#!/usr/bin/env python3
"""
Upload automático de processos SEI → AnalyticSEI
==============================================
Navega o SEI com Playwright (Chromium headless), troca de setor clicando
no link de unidade no topo da tela, percorre TODAS as páginas (100/página)
e faz upload para a API do AnalyticSEI via API key.

Credenciais via variáveis de ambiente (GitHub Secrets) — nunca no código.

Troca de coordenador:
    Basta atualizar SEI_USER e SEI_PASSWORD nos GitHub Secrets.

Variáveis de ambiente necessárias:
    SEI_URL       URL base do SEI    (sem barra final)
    SEI_USER      Login SEI
    SEI_PASSWORD  Senha SEI
    BI_API_URL    URL da API do AnalyticSEI
    BI_API_KEY    API key (variável API_UPLOAD_KEY no Render)
"""

import asyncio
import csv
import io
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
import unicodedata

import httpx
from playwright.async_api import Error as PlaywrightError, async_playwright, TimeoutError as PlaywrightTimeout

DEFAULT_BI_API_URL = "https://bi-copag-api.onrender.com"
DEFAULT_ARTIFACT_DIR = "artifacts/sei-upload"
DEFAULT_SETOR_RETRIES = 3
LEGACY_BI_API_URLS = {
    "https://sei-bi-copag-andersoncfs-api.onrender.com",
}


def bi_base_url() -> str:
    url = os.getenv("BI_API_URL", DEFAULT_BI_API_URL).rstrip("/")
    if url in LEGACY_BI_API_URLS:
        print(f"  Aviso: BI_API_URL aponta para serviço antigo/suspenso ({url}).")
        print(f"  Usando API ativa: {DEFAULT_BI_API_URL}")
        return DEFAULT_BI_API_URL
    return url


def artifact_dir() -> Path:
    return Path(os.getenv("SEI_UPLOAD_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR))


def setor_retries() -> int:
    raw = os.getenv("SEI_UPLOAD_SETOR_RETRIES", str(DEFAULT_SETOR_RETRIES))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_SETOR_RETRIES


def _safe_filename(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value or "sem-nome"


def _sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    sensitive = {"infra_hash", "hash", "ticket", "senha", "password"}
    query = [
        (key, "***" if key.lower() in sensitive else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunparse(parsed._replace(query=urlencode(query)))


def inferir_sei_base(sei_url: str, current_url: str) -> str:
    """Define a base do módulo SEI, evitando usar /sip/login.php como base."""
    env_base = sei_url.rstrip("/")
    parsed_env = urlparse(env_base)
    if parsed_env.path and parsed_env.path != "/":
        return env_base

    parsed_current = urlparse(current_url)
    path = parsed_current.path
    if "/controlador.php" in path:
        base_path = path.rsplit("/controlador.php", 1)[0]
    elif path.endswith("/login.php") and "/sip/" not in path:
        base_path = path.rsplit("/login.php", 1)[0]
    elif path.startswith("/sei/"):
        base_path = "/sei"
    else:
        base_path = parsed_env.path.rstrip("/")

    return f"{parsed_current.scheme}://{parsed_current.netloc}{base_path}".rstrip("/")

# ---------------------------------------------------------------------------
# Mapeamento: código do setor no AnalyticSEI → nome exato da unidade no SEI
# Nomes confirmados na inspeção do DevTools em 06/05/2026
# ---------------------------------------------------------------------------
# Coluna 1: código do setor no AnalyticSEI
# Coluna 2: sigla exata do label na página de troca de unidade (title="SIGLA")
# Confirmado via DevTools em 06/05/2026
SETORES = [
    ("DIAPE",            "DIAPE"),
    ("DICAT",            "DICAT"),
    ("DIJOR",            "DIJOR"),
    ("DICAF",            "DICAF"),
    ("DICAF-CHEFIA",     "DICAF-CHEFIA"),
    ("DICAF-REPOSICOES", "DICAF-REPOSIÇÕES"),   # acento confirmado no title
]

# ---------------------------------------------------------------------------
# Cabeçalho CSV esperado pelo AnalyticSEI (não alterar)
# ---------------------------------------------------------------------------
CABECALHO = [
    "ID", "Protocolo", "Atribuicao", "Tipo", "Especificacao",
    "Ponto_Controle", "Data_Autuacao", "Data_Recebimento",
    "Data_Envio", "Unidade_Envio", "Observacoes",
]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def _is_navigation_abort(exc: Exception) -> bool:
    return "net::ERR_ABORTED" in str(exc)


async def goto_tolerante(page, url: str, *, wait_until: str = "domcontentloaded", timeout: int = 30_000) -> None:
    """Navega tolerando abortos causados por redirecionamentos do SEI."""
    try:
        await page.goto(url, wait_until=wait_until, timeout=timeout)
    except PlaywrightError as exc:
        if not _is_navigation_abort(exc):
            raise
        print("  Aviso: navegação abortada pelo SEI; aguardando página estabilizar...")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightTimeout:
            pass


async def selector_existe(page, selector: str) -> bool:
    try:
        return await page.locator(selector).count() > 0
    except PlaywrightError:
        return False


async def listar_unidades_visiveis(page) -> list[dict]:
    try:
        return await page.evaluate("""
            () => Array.from(document.querySelectorAll('label.infraRadioLabel'))
                .map((el) => ({
                    title: el.getAttribute('title') || '',
                    text: (el.textContent || '').trim(),
                    for_attr: el.getAttribute('for') || '',
                }))
                .filter((item) => item.title || item.text)
        """)
    except PlaywrightError:
        return []


async def salvar_diagnostico(
    page, setor: str, fase: str, tentativa: int, erro=None, *, capturar_screenshot: bool = True
) -> None:
    """Salva evidências úteis para depurar falhas do SEI no GitHub Actions."""
    if os.getenv("SEI_UPLOAD_DIAGNOSTICS", "1").lower() in {"0", "false", "no"}:
        return

    out_dir = artifact_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{date.today().isoformat()}_{_safe_filename(setor)}_tentativa-{tentativa}_{_safe_filename(fase)}"

    screenshot_error = ""
    if capturar_screenshot:
        try:
            await page.screenshot(path=str(out_dir / f"{prefix}.png"), full_page=True, timeout=10_000)
        except Exception as exc:
            screenshot_error = f"Falha ao capturar screenshot: {type(exc).__name__}: {exc}"

    unidades = await listar_unidades_visiveis(page)
    selectors = {
        "#txtUsuario": await selector_existe(page, "#txtUsuario"),
        "#lnkInfraUnidade": await selector_existe(page, "#lnkInfraUnidade"),
        "label.infraRadioLabel": await selector_existe(page, "label.infraRadioLabel"),
        "#divRecebidos": await selector_existe(page, "#divRecebidos"),
        "#tblProcessosRecebidos": await selector_existe(page, "#tblProcessosRecebidos"),
    }
    try:
        title = await page.title()
    except PlaywrightError:
        title = ""

    linhas = [
        f"Setor: {setor}",
        f"Fase: {fase}",
        f"Tentativa: {tentativa}",
        f"URL atual: {_sanitize_url(page.url)}",
        f"Título: {title}",
        f"Erro: {erro}",
        f"Screenshot: {'não capturado' if screenshot_error or not capturar_screenshot else prefix + '.png'}",
        screenshot_error,
        "",
        "Seletores encontrados:",
        *[f"- {selector}: {existe}" for selector, existe in selectors.items()],
        "",
        f"Unidades encontradas ({len(unidades)}):",
        *[
            f"- title='{item.get('title', '')}' text='{item.get('text', '')}' for='{item.get('for_attr', '')}'"
            for item in unidades[:120]
        ],
    ]
    (out_dir / f"{prefix}.txt").write_text("\n".join(linhas), encoding="utf-8")

    if os.getenv("SEI_UPLOAD_SAVE_HTML", "0").lower() in {"1", "true", "yes"}:
        try:
            html = await page.content()
            (out_dir / f"{prefix}.html").write_text(html, encoding="utf-8")
        except PlaywrightError:
            pass


async def preparar_area_recebidos(page) -> None:
    """Garante que a área de recebidos não fique oculta por CSS responsivo."""
    await page.evaluate("""
        () => {
            const div = document.getElementById('divRecebidos');
            if (div) {
                div.classList.remove('d-none');
                div.style.display = 'block';
                div.style.visibility = 'visible';
            }
            const table = document.getElementById('tblProcessosRecebidos');
            if (table) {
                table.style.visibility = 'visible';
            }
        }
    """)


async def aguardar_painel_processos(page, sei_base: str, *, timeout: int = 45_000) -> None:
    """Confirma que a sessão chegou à tela com a tabela de processos recebidos."""
    if "infra_trocar_unidade" in page.url or page.url.endswith("/login.php") or "login.php" in page.url:
        await goto_tolerante(
            page,
            f"{sei_base}/controlador.php?acao=procedimento_controlar",
            wait_until="domcontentloaded",
            timeout=45_000,
        )

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except PlaywrightTimeout:
        pass

    if await selector_existe(page, "#txtUsuario"):
        raise RuntimeError("Sessão voltou para a tela de login do SEI.")

    await preparar_area_recebidos(page)
    try:
        await page.wait_for_selector("#tblProcessosRecebidos", state="attached", timeout=timeout)
    except PlaywrightTimeout as exc:
        unidades = await listar_unidades_visiveis(page)
        resumo_unidades = ", ".join(
            item.get("title") or item.get("text") or "sem título"
            for item in unidades[:12]
        )
        raise RuntimeError(
            "Painel de processos não carregou após troca de unidade. "
            f"URL atual: {_sanitize_url(page.url)}. "
            f"Unidades visíveis: {resumo_unidades or 'nenhuma'}"
        ) from exc


async def garantir_painel_logado(page, sei_url: str, sei_user: str, sei_pass: str, sei_base: str) -> str:
    """Garante sessão autenticada e navegação no painel antes de processar um setor."""
    if await selector_existe(page, "#txtUsuario") or "/sip/login.php" in page.url:
        print("  Aviso: sessão no SEI voltou para login; refazendo autenticação...")
        await fazer_login(page, sei_url, sei_user, sei_pass)
        sei_base = inferir_sei_base(sei_url, page.url)

    painel_url = f"{sei_base}/controlador.php?acao=procedimento_controlar"
    await goto_tolerante(page, painel_url, wait_until="domcontentloaded", timeout=45_000)
    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeout:
        pass

    if await selector_existe(page, "#txtUsuario"):
        print("  Aviso: painel redirecionou para login; refazendo autenticação...")
        await fazer_login(page, sei_url, sei_user, sei_pass)
        sei_base = inferir_sei_base(sei_url, page.url)

    return sei_base

async def fazer_login(page, sei_url: str, sei_user: str, sei_pass: str) -> None:
    """Faz login no SEI.

    A URL de login é sempre /sip/login.php na raiz do domínio,
    independente do caminho em SEI_URL (ex: /sei).
    """
    parsed  = urlparse(sei_url)
    dominio = f"{parsed.scheme}://{parsed.netloc}"   # ex: https://sei.ufc.br
    login_url = (
        f"{dominio}/sip/login.php"
        "?sigla_orgao_sistema=UFC&sigla_sistema=SEI"
    )
    print(f"  → Acessando: {login_url}")
    await goto_tolerante(page, login_url, wait_until="domcontentloaded")
    await page.wait_for_selector("#txtUsuario", timeout=30_000)
    await page.fill("#txtUsuario", sei_user)
    await page.fill("#pwdSenha",   sei_pass)
    await page.click("#sbmAcessar")
    try:
        await page.wait_for_load_state("networkidle", timeout=20_000)
    except PlaywrightTimeout:
        pass

    if "login" in page.url.lower():
        raise RuntimeError("Login falhou — verifique SEI_USER e SEI_PASSWORD.")
    print(f"  ✓ Login realizado. URL atual: {page.url}")


# ---------------------------------------------------------------------------
# Troca de unidade
# ---------------------------------------------------------------------------

async def trocar_para_setor(page, sei_base: str, sigla: str) -> None:
    """
    Navega para a página de troca de unidade e clica no label da sigla-alvo.

    Seletores confirmados via DevTools (06/05/2026):
      label[title="DIAPE"], label[title="DICAT"], label[title="DIJOR"],
      label[title="DICAF"], label[title="DICAF-CHEFIA"],
      label[title="DICAF-REPOSIÇÕES"]

    O clique no label aciona o radio button e o SEI redireciona
    automaticamente ao painel da divisão — sem botão de confirmação.
    """
    # 1. Extrai a URL de troca de unidade do onclick (evita clicar em
    #    elemento que está invisível em headless).
    onclick_url: str | None = await page.evaluate("""
        () => {
            const el = document.getElementById('lnkInfraUnidade');
            if (!el) return null;
            const m = (el.getAttribute('onclick') || '').match(/location\\.href='([^']+)'/);
            return m ? m[1] : null;
        }
    """)

    if onclick_url:
        destino = onclick_url if onclick_url.startswith("http") else urljoin(f"{sei_base}/", onclick_url)
        await goto_tolerante(page, destino, wait_until="domcontentloaded", timeout=45_000)
    else:
        await page.evaluate(
            "() => { const el = document.getElementById('lnkInfraUnidade'); if (el) el.click(); }"
        )

    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeout:
        pass

    # Aguarda a lista de labels aparecer antes de procurar a sigla específica
    try:
        await page.wait_for_selector("label.infraRadioLabel", timeout=15_000)
    except PlaywrightTimeout:
        pass  # sem labels visíveis — a tentativa de clique abaixo vai falhar com mensagem clara

    # 2. Clica no label/radio da sigla-alvo via JS (ignora visibilidade
    #    headless e normaliza acentos, ex: REPOSIÇÕES == REPOSICOES).
    #    O clique dispara a navegação de volta ao painel — não há submit button.
    result = await page.evaluate(
        """(sigla) => {
            const normalize = (value) => (value || '')
                .normalize('NFD')
                .replace(/[\\u0300-\\u036f]/g, '')
                .replace(/\\s+/g, '')
                .toUpperCase();
            const target = normalize(sigla);
            const labels = Array.from(document.querySelectorAll('label.infraRadioLabel'));
            for (const label of labels) {
                const candidates = [
                    label.getAttribute('title') || '',
                    label.textContent || '',
                    label.getAttribute('for') || '',
                ];
                if (candidates.some((candidate) => normalize(candidate) === target)) {
                    const inputId = label.getAttribute('for');
                    const input = inputId ? document.getElementById(inputId) : null;
                    if (input) input.click();
                    label.click();
                    return {
                        clicked: true,
                        title: label.getAttribute('title') || '',
                        text: (label.textContent || '').trim(),
                    };
                }
            }
            return {
                clicked: false,
                unidades: labels.map((label) => ({
                    title: label.getAttribute('title') || '',
                    text: (label.textContent || '').trim(),
                    for_attr: label.getAttribute('for') || '',
                })),
            };
        }""",
        sigla,
    )

    if not result.get("clicked"):
        unidades = result.get("unidades") or await listar_unidades_visiveis(page)
        disponiveis = ", ".join(
            item.get("title") or item.get("text") or "sem título"
            for item in unidades[:40]
        )
        raise RuntimeError(
            f"Sigla '{sigla}' não encontrada na página de seleção de unidade. "
            f"Disponíveis: {disponiveis or 'nenhuma'}."
        )

    # 3. Aguarda a navegação de volta ao painel da divisão
    try:
        await page.wait_for_load_state("networkidle", timeout=20_000)
    except PlaywrightTimeout:
        pass

    # Caso especial: se a unidade já era a ativa, o SEI pode manter a URL
    # em infra_trocar_unidade ao invés de redirecionar ao painel.
    # Também tratamos login.php porque o SEI pode passar por uma tela
    # intermediária antes de voltar ao controlador.
    await aguardar_painel_processos(page, sei_base, timeout=60_000)

    print(f"  ✓ Unidade: {sigla}  (URL: {page.url.split('?')[0].split('/')[-1]})")


# ---------------------------------------------------------------------------
# Extração de dados de uma linha da tabela de processos
# ---------------------------------------------------------------------------

async def extrair_linha(row) -> dict | None:
    """
    Extrai dados de uma linha <tr> da tabela de processos recebidos.

    Estrutura observada no DevTools:
      td[0] → checkbox: title="PROTOCOLO", aria-label="... / Tipo X / Especificação Y"
      td[1] → ícones de status (ignorado)
      td[2] → link do processo (número formatado com <wbr>)
      td[3] → atribuição: <a title="Atribuído para NOME">sigla</a> ou &nbsp;
    """
    checkbox = await row.query_selector("input[type='checkbox']")
    if not checkbox:
        return None

    # Protocolo (ex: "23067.021001/2026-66")
    protocolo = (await checkbox.get_attribute("title") or "").strip()
    if not protocolo:
        return None

    # ID interno do processo (value do checkbox)
    process_id = (await checkbox.get_attribute("value") or "").strip()

    # Tipo e Especificação — extraídos do aria-label
    aria = (await checkbox.get_attribute("aria-label") or "")
    tipo         = ""
    especificacao = ""
    for parte in aria.split(" / "):
        if parte.startswith("Tipo "):
            tipo = parte[5:].strip()
        elif parte.startswith("Especificação "):
            especificacao = parte[14:].strip()

    # Atribuição — 4ª coluna: <a title="Atribuído para NOME">
    atribuicao = ""
    atrib_link = await row.query_selector("td:nth-child(4) a[title]")
    if atrib_link:
        atrib_title = (await atrib_link.get_attribute("title") or "").strip()
        if atrib_title.startswith("Atribuído para "):
            atribuicao = atrib_title[15:].strip()

    return {
        "ID":               process_id,
        "Protocolo":        protocolo,
        "Atribuicao":       atribuicao,
        "Tipo":             tipo,
        "Especificacao":    especificacao,
        "Ponto_Controle":   "",  # não disponível nesta view
        "Data_Autuacao":    "",  # não disponível nesta view
        "Data_Recebimento": "",  # não disponível nesta view
        "Data_Envio":       "",  # não disponível nesta view
        "Unidade_Envio":    "",  # não disponível nesta view
        "Observacoes":      "",  # não disponível nesta view
    }


# ---------------------------------------------------------------------------
# Coleta de todos os processos (com paginação)
# ---------------------------------------------------------------------------

async def coletar_todos_processos(page) -> list[dict]:
    """
    Percorre TODAS as páginas da tabela #tblProcessosRecebidos.
    A paginação usa o link #lnkRecebidosProximaPaginaSuperior.
    """
    todos: list[dict] = []
    pagina = 1

    # Força visibilidade do divRecebidos — o Bootstrap usa d-none d-md-block
    # e em alguns casos a div pode ser renderizada como oculta mesmo em
    # viewport largo (headless). O JS garante que o elemento fique visível.
    await preparar_area_recebidos(page)

    # Aguarda a tabela de processos aparecer.
    # Todos os setores sempre têm processos — se a tabela não carregar é erro.
    # Timeout de 60 s para tolerar variações de latência do SEI.
    await page.wait_for_selector("#tblProcessosRecebidos", state="attached", timeout=60_000)

    while True:
        print(f"    Página {pagina}...")

        rows = await page.query_selector_all(
            "#tblProcessosRecebidos tbody tr"
        )

        for row in rows:
            dado = await extrair_linha(row)
            if dado:
                todos.append(dado)

        # Próxima página
        proximo = await page.query_selector(
            "#lnkRecebidosProximaPaginaSuperior"
        )
        if not proximo or not await proximo.is_visible():
            break

        await proximo.click()
        await page.wait_for_load_state("networkidle")
        pagina += 1

    print(f"    ✓ {len(todos)} processos coletados em {pagina} página(s)")
    return todos


# ---------------------------------------------------------------------------
# Geração do CSV
# ---------------------------------------------------------------------------

def montar_csv(processos: list[dict]) -> bytes:
    """Serializa a lista de processos no formato CSV esperado pelo AnalyticSEI."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CABECALHO, delimiter=";",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(processos)
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Upload para o AnalyticSEI
# ---------------------------------------------------------------------------

async def upload_para_bi(
    bi_url: str, bi_key: str, setor: str, data_str: str, csv_bytes: bytes
) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{bi_url}/api/upload-with-key",
            data={"setor": setor, "data_relatorio": data_str},
            files={"file": (f"processos_{setor}_{data_str}.csv",
                            csv_bytes, "text/csv")},
            headers={"X-Api-Key": bi_key},
        )
        r.raise_for_status()
        res = r.json()
        status_label = {
            "imported":  "importado",
            "replaced":  "substituído",
            "duplicate": "duplicado (ignorado)",
        }.get(res.get("status", ""), res.get("status", ""))
        print(
            f"  ✓ {setor}: {res.get('total_registros', 0)} processos"
            f" — {status_label}"
        )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

async def main() -> None:
    sei_url  = os.environ["SEI_URL"].rstrip("/")
    sei_user = os.environ["SEI_USER"]
    sei_pass = os.environ["SEI_PASSWORD"]
    bi_url   = bi_base_url()
    bi_key   = os.environ["BI_API_KEY"]
    hoje     = date.today().isoformat()

    print(f"=== Upload automático SEI → AnalyticSEI | {hoje} ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def criar_pagina():
            # Viewport explícito acima de 768 px para que Bootstrap d-md-block funcione.
            return await browser.new_page(viewport={"width": 1440, "height": 900})

        page = await criar_pagina()

        print("Fazendo login no SEI...")
        await fazer_login(page, sei_url, sei_user, sei_pass)

        # Base URL do SEI (ex: https://sei.ufc.br/sei)
        # Derivada da URL atual após login, mas protegida contra /sip/login.php.
        sei_base = inferir_sei_base(sei_url, page.url)
        print(f"  → SEI base: {sei_base}")

        async def resetar_pagina() -> bool:
            """Navega ao painel principal com verificação real de sessão."""
            nonlocal sei_base
            try:
                sei_base = await garantir_painel_logado(page, sei_url, sei_user, sei_pass, sei_base)
                return True
            except Exception as exc:
                print(f"  Aviso: reset do painel falhou ({type(exc).__name__}: {exc}).")
                return False

        async def nova_sessao() -> None:
            """Abre uma página limpa e refaz login para evitar efeito cascata."""
            nonlocal page, sei_base
            try:
                await page.close()
            except Exception:
                pass
            page = await criar_pagina()
            print("  ↻ Refazendo login em nova página para limpar estado do SEI...")
            await fazer_login(page, sei_url, sei_user, sei_pass)
            sei_base = inferir_sei_base(sei_url, page.url)

        erros: list[str] = []
        max_tentativas = setor_retries()
        for bi_setor, sigla_sei in SETORES:
            print(f"\n--- {bi_setor} ---")
            ultimo_erro = ""
            for tentativa in range(1, max_tentativas + 1):
                if tentativa > 1:
                    print(f"  ↻ Nova tentativa {tentativa}/{max_tentativas} para {bi_setor}...")

                try:
                    sei_base = await garantir_painel_logado(page, sei_url, sei_user, sei_pass, sei_base)
                    await trocar_para_setor(page, sei_base, sigla_sei)
                    processos = await coletar_todos_processos(page)
                    if not processos:
                        raise RuntimeError("Extração retornou 0 processos — tabela carregou vazia.")
                    csv_bytes = montar_csv(processos)
                    await upload_para_bi(bi_url, bi_key, bi_setor, hoje, csv_bytes)
                    ultimo_erro = ""
                    break
                except PlaywrightTimeout as exc:
                    ultimo_erro = f"{bi_setor}: timeout — {exc}"
                    print(f"  ✗ {ultimo_erro}")
                    await salvar_diagnostico(page, bi_setor, "timeout", tentativa, exc)
                except PlaywrightError as exc:
                    ultimo_erro = f"{bi_setor}: erro de navegação no SEI — {exc}"
                    print(f"  ✗ {ultimo_erro}")
                    await salvar_diagnostico(page, bi_setor, "erro-navegacao", tentativa, exc)
                except httpx.HTTPError as exc:
                    ultimo_erro = f"{bi_setor}: erro no upload — {exc}"
                    print(f"  ✗ {ultimo_erro}")
                    await salvar_diagnostico(
                        page, bi_setor, "erro-upload", tentativa, exc, capturar_screenshot=False
                    )
                except RuntimeError as exc:
                    ultimo_erro = f"{bi_setor}: {exc}"
                    print(f"  ✗ {ultimo_erro}")
                    await salvar_diagnostico(page, bi_setor, "erro-runtime", tentativa, exc)

                if tentativa < max_tentativas:
                    reset_ok = await resetar_pagina()
                    if not reset_ok or tentativa >= 2 or await selector_existe(page, "#txtUsuario"):
                        await nova_sessao()
                else:
                    erros.append(ultimo_erro)

        await browser.close()

    print("\n=== Concluído ===")
    if erros:
        print(f"\nErros encontrados ({len(erros)}):")
        for e in erros:
            print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

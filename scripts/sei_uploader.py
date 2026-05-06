#!/usr/bin/env python3
"""
Upload automático de processos SEI → BI COPAG
==============================================
Navega o SEI com Playwright (Chromium headless), troca de setor clicando
no link de unidade no topo da tela, percorre TODAS as páginas (100/página)
e faz upload para a API do BI via API key.

Credenciais via variáveis de ambiente (GitHub Secrets) — nunca no código.

Troca de coordenador:
    Basta atualizar SEI_USER e SEI_PASSWORD nos GitHub Secrets.

Variáveis de ambiente necessárias:
    SEI_URL       URL base do SEI    (sem barra final)
    SEI_USER      Login SEI
    SEI_PASSWORD  Senha SEI
    BI_API_URL    URL da API do BI
    BI_API_KEY    API key (variável API_UPLOAD_KEY no Render)
"""

import asyncio
import csv
import io
import os
import sys
from datetime import date
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Mapeamento: código do setor no BI → nome exato da unidade no SEI
# Nomes confirmados na inspeção do DevTools em 06/05/2026
# ---------------------------------------------------------------------------
# Coluna 1: código do setor no BI COPAG
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
# Cabeçalho CSV esperado pelo BI COPAG (não alterar)
# ---------------------------------------------------------------------------
CABECALHO = [
    "ID", "Protocolo", "Atribuicao", "Tipo", "Especificacao",
    "Ponto_Controle", "Data_Autuacao", "Data_Recebimento",
    "Data_Envio", "Unidade_Envio", "Observacoes",
]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

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
    await page.goto(login_url, wait_until="domcontentloaded")
    await page.wait_for_selector("#txtUsuario", timeout=30_000)
    await page.fill("#txtUsuario", sei_user)
    await page.fill("#pwdSenha",   sei_pass)
    await page.click("#sbmAcessar")
    await page.wait_for_load_state("networkidle")

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
        await page.goto(f"{sei_base}/{onclick_url}", wait_until="domcontentloaded")
    else:
        await page.evaluate(
            "() => { const el = document.getElementById('lnkInfraUnidade'); if (el) el.click(); }"
        )

    await page.wait_for_load_state("networkidle")

    # 2. Clica no label da sigla-alvo via JS (ignora visibilidade headless).
    #    O clique dispara a navegação de volta ao painel — não há submit button.
    clicked: bool = await page.evaluate(
        """(sigla) => {
            const el = document.querySelector('label[title="' + sigla + '"]');
            if (el) { el.click(); return true; }
            return false;
        }""",
        sigla,
    )

    if not clicked:
        raise RuntimeError(
            f"Sigla '{sigla}' não encontrada na página de seleção de unidade."
        )

    # 3. Aguarda a navegação de volta ao painel da divisão
    await page.wait_for_load_state("networkidle")
    print(f"  ✓ Unidade: {sigla}")


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

    # Aguarda a tabela de processos aparecer antes de começar a coleta.
    # O SEI pode fazer navegações internas adicionais após trocar de unidade.
    await page.wait_for_selector("#tblProcessosRecebidos", timeout=30_000)

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
    """Serializa a lista de processos no formato CSV esperado pelo BI COPAG."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CABECALHO, delimiter=";",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(processos)
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Upload para o BI COPAG
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
    bi_url   = os.environ["BI_API_URL"]
    bi_key   = os.environ["BI_API_KEY"]
    hoje     = date.today().isoformat()

    print(f"=== Upload automático SEI → BI COPAG | {hoje} ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        print("Fazendo login no SEI...")
        await fazer_login(page, sei_url, sei_user, sei_pass)

        # Base URL do SEI (ex: https://sei.ufc.br/sei)
        # Derivada da URL atual após login para não hardcodar o caminho
        sei_base = page.url.rsplit("/", 1)[0]
        print(f"  → SEI base: {sei_base}")

        erros: list[str] = []
        for bi_setor, sigla_sei in SETORES:
            print(f"\n--- {bi_setor} ---")
            try:
                await trocar_para_setor(page, sei_base, sigla_sei)
                processos  = await coletar_todos_processos(page)
                if not processos:
                    print("  ⚠ Nenhum processo encontrado — setor ignorado.")
                    continue
                csv_bytes  = montar_csv(processos)
                await upload_para_bi(bi_url, bi_key, bi_setor, hoje, csv_bytes)
            except PlaywrightTimeout as exc:
                msg = f"{bi_setor}: timeout — {exc}"
                print(f"  ✗ {msg}")
                erros.append(msg)
            except httpx.HTTPError as exc:
                msg = f"{bi_setor}: erro no upload — {exc}"
                print(f"  ✗ {msg}")
                erros.append(msg)
            except RuntimeError as exc:
                msg = f"{bi_setor}: {exc}"
                print(f"  ✗ {msg}")
                erros.append(msg)

        await browser.close()

    print("\n=== Concluído ===")
    if erros:
        print(f"\nErros encontrados ({len(erros)}):")
        for e in erros:
            print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

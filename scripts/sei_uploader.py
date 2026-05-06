#!/usr/bin/env python3
"""
Upload automático de processos SEI → BI COPAG
==============================================
Navega o SEI com Playwright (Chromium headless), troca de setor pelo
seletor do topo da tela, coleta TODOS os processos de TODAS as páginas
(paginação 100/página) e faz upload para a API do BI via API key.

Credenciais via variáveis de ambiente (GitHub Secrets) — nunca no código.

Troca de coordenador:
    Basta atualizar SEI_USER e SEI_PASSWORD nos GitHub Secrets.
    Nenhum arquivo de código precisa ser alterado.

Variáveis de ambiente necessárias:
    SEI_URL       URL base do SEI    ex: https://sei.ufc.br/sei
    SEI_USER      Login SEI
    SEI_PASSWORD  Senha SEI
    BI_API_URL    URL da API do BI   ex: https://sei-bi-copag-andersoncfs-api.onrender.com
    BI_API_KEY    API key configurada no Render (variável API_UPLOAD_KEY)

Ajuste obrigatório antes do primeiro uso:
    Os seletores CSS marcados com  # ⚠️ CONFIRMAR  precisam ser verificados
    abrindo o SEI no Chrome → DevTools (F12) → inspecionar os elementos.
"""

import asyncio
import csv
import io
import os
import sys
from datetime import date

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Configuração dos setores
# Coluna 1: código do setor no BI COPAG
# Coluna 2: nome exato da unidade como aparece no seletor do SEI
# ⚠️ CONFIRMAR os nomes após inspecionar o seletor de unidade no SEI
# ---------------------------------------------------------------------------
SETORES = [
    ("DIAPE",            "COPAG - DIAPE"),
    ("DICAT",            "COPAG - DICAT"),
    ("DIJOR",            "COPAG - DIJOR"),
    ("DICAF",            "COPAG - DICAF"),
    ("DICAF-CHEFIA",     "COPAG - DICAF (Chefia)"),
    ("DICAF-REPOSICOES", "COPAG - DICAF Reposições"),
]

# ---------------------------------------------------------------------------
# Cabeçalho CSV esperado pelo BI COPAG (não alterar)
# ---------------------------------------------------------------------------
CABECALHO_CSV = [
    "ID", "Protocolo", "Atribuicao", "Tipo", "Especificacao",
    "Ponto_Controle", "Data_Autuacao", "Data_Recebimento",
    "Data_Envio", "Unidade_Envio", "Observacoes",
]

# ---------------------------------------------------------------------------
# Mapeamento: índice da coluna na tabela HTML do SEI → campo do CSV do BI
# ⚠️ CONFIRMAR após inspecionar a tabela de processos no SEI
# Exemplo: se a 2ª coluna (índice 1) é "Processo/Documento" → "Protocolo"
# ---------------------------------------------------------------------------
COLUNA_MAP: dict[int, str] = {
    # índice : nome_no_csv
    # 0: "ID",          # descomente e ajuste conforme necessário
    # 1: "Protocolo",
    # 2: "Tipo",
    # 3: "Atribuicao",
    # 4: "Especificacao",
}


# ---------------------------------------------------------------------------
# Funções de navegação no SEI
# ---------------------------------------------------------------------------

async def fazer_login(page, sei_url: str, sei_user: str, sei_pass: str) -> None:
    """Faz login no SEI com usuário e senha."""
    await page.goto(f"{sei_url}/login.php")           # ⚠️ CONFIRMAR URL de login
    await page.fill("#txtUsuario", sei_user)           # ⚠️ CONFIRMAR seletor do campo usuário
    await page.fill("#pwdSenha", sei_pass)             # ⚠️ CONFIRMAR seletor da senha
    await page.click("#sbmLogin")                      # ⚠️ CONFIRMAR seletor do botão login
    await page.wait_for_load_state("networkidle")

    # Verificação básica: se ainda estiver na página de login, algo errou
    if "login" in page.url.lower():
        raise RuntimeError("Login falhou — verifique SEI_USER e SEI_PASSWORD.")

    print("  ✓ Login realizado.")


async def trocar_para_setor(page, nome_unidade: str) -> None:
    """Clica no seletor de unidade no topo do SEI e escolhe a divisão."""
    # ⚠️ CONFIRMAR os seletores abaixo após inspecionar o botão de troca de unidade
    await page.click("#lnkInfraMenuSistema")           # ⚠️ botão/link no topo
    await page.wait_for_selector("#frmAlterarUnidade") # ⚠️ formulário/modal que abre
    await page.select_option(
        "select[name='selUnidade']",                   # ⚠️ seletor do <select> de unidades
        label=nome_unidade,
    )
    await page.click("button[type='submit']")          # ⚠️ botão confirmar
    await page.wait_for_load_state("networkidle")


async def coletar_todos_processos(page) -> list[list[str]]:
    """Coleta todos os processos iterando por TODAS as páginas (100/página)."""
    todos: list[list[str]] = []
    pagina = 1

    while True:
        print(f"    Página {pagina}...")

        # Extrai todas as linhas da tabela de processos da página atual
        # ⚠️ CONFIRMAR o seletor da tabela de processos
        linhas: list[list[str]] = await page.eval_on_selector_all(
            "table#tabelaProcessos tbody tr",          # ⚠️ CONFIRMAR seletor da tabela
            "rows => rows.map(r => Array.from(r.cells).map(c => c.innerText.trim()))",
        )
        todos.extend(linhas)

        # Verifica se existe botão/link de "Próxima página"
        # ⚠️ CONFIRMAR o seletor do link de próxima página
        proximo = await page.query_selector("a[title='Próxima página']")  # ⚠️ CONFIRMAR
        if not proximo:
            break  # Última página alcançada

        await proximo.click()
        await page.wait_for_load_state("networkidle")
        pagina += 1

    print(f"    ✓ {len(todos)} processos coletados em {pagina} página(s)")
    return todos


# ---------------------------------------------------------------------------
# Geração do CSV
# ---------------------------------------------------------------------------

def montar_csv(linhas: list[list[str]]) -> bytes:
    """Converte as linhas extraídas do SEI para CSV no formato do BI COPAG."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(CABECALHO_CSV)

    for linha in linhas:
        row = [""] * len(CABECALHO_CSV)
        for idx, col_nome in COLUNA_MAP.items():
            if idx < len(linha) and col_nome in CABECALHO_CSV:
                row[CABECALHO_CSV.index(col_nome)] = linha[idx]
        writer.writerow(row)

    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Upload para o BI COPAG
# ---------------------------------------------------------------------------

async def upload_para_bi(
    bi_url: str,
    bi_key: str,
    setor: str,
    data_str: str,
    csv_bytes: bytes,
) -> None:
    """Envia o CSV para a API do BI COPAG via API key."""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{bi_url}/api/upload-with-key",
            data={"setor": setor, "data_relatorio": data_str},
            files={"file": (f"processos_{setor}_{data_str}.csv", csv_bytes, "text/csv")},
            headers={"X-Api-Key": bi_key},
        )
        r.raise_for_status()
        res = r.json()
        status_label = {"imported": "importado", "replaced": "substituído",
                        "duplicate": "duplicado (ignorado)"}.get(res.get("status", ""), res.get("status", ""))
        print(f"  ✓ {setor}: {res.get('total_registros', 0)} processos — {status_label}")


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

async def main() -> None:
    sei_url  = os.environ["SEI_URL"]
    sei_user = os.environ["SEI_USER"]       # GitHub Secret — atualizar na troca de coordenador
    sei_pass = os.environ["SEI_PASSWORD"]   # GitHub Secret — atualizar na troca de coordenador
    bi_url   = os.environ["BI_API_URL"]
    bi_key   = os.environ["BI_API_KEY"]
    hoje     = date.today().isoformat()

    print(f"=== Upload automático SEI → BI COPAG | {hoje} ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        # 1. Login
        print("Login no SEI...")
        await fazer_login(page, sei_url, sei_user, sei_pass)

        # 2. Para cada setor: trocar → coletar → enviar
        erros: list[str] = []
        for bi_setor, nome_sei in SETORES:
            print(f"\n--- {bi_setor} ({nome_sei}) ---")
            try:
                await trocar_para_setor(page, nome_sei)
                linhas    = await coletar_todos_processos(page)
                if not linhas:
                    print(f"  ⚠ Nenhum processo encontrado — setor ignorado.")
                    continue
                csv_bytes = montar_csv(linhas)
                await upload_para_bi(bi_url, bi_key, bi_setor, hoje, csv_bytes)
            except PlaywrightTimeout as exc:
                msg = f"{bi_setor}: timeout ao navegar — {exc}"
                print(f"  ✗ {msg}")
                erros.append(msg)
            except httpx.HTTPError as exc:
                msg = f"{bi_setor}: erro no upload — {exc}"
                print(f"  ✗ {msg}")
                erros.append(msg)

        await browser.close()

    print("\n=== Concluído ===")
    if erros:
        print(f"\nErros ({len(erros)}):")
        for e in erros:
            print(f"  - {e}")
        sys.exit(1)  # Faz o GitHub Actions marcar o job como falho → dispara e-mail de alerta


if __name__ == "__main__":
    asyncio.run(main())

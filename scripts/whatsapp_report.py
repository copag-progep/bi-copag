#!/usr/bin/env python3
"""
Relatório diário WhatsApp — BI COPAG
=====================================
Coleta o resumo diário do endpoint /api/reports/daily-summary e formata
uma mensagem compacta para WhatsApp.

Modo --dry-run (padrão quando as variáveis WhatsApp não estão configuradas):
    imprime o texto que seria enviado — não toca a API da Meta.

Modo produção (quando WHATSAPP_TOKEN e WHATSAPP_PHONE_ID estiverem nos Secrets):
    envia um template aprovado via WhatsApp Cloud API (Meta) para cada número
    listado em WHATSAPP_RECIPIENTS.

Variáveis de ambiente:
    BI_API_URL           URL da API do BI (ex: https://bi-copag-api.onrender.com)
    BI_API_KEY           API key do BI (mesma que API_UPLOAD_KEY no Render)
    WHATSAPP_TOKEN       Bearer token da Meta Cloud API
    WHATSAPP_PHONE_ID    Phone Number ID da Meta
    WHATSAPP_RECIPIENTS  Números separados por vírgula (+5585999999999,+5585888888888)
    WHATSAPP_TEMPLATE    Nome do template aprovado (padrão: bi_copag_daily_report)
"""

import argparse
import os
import sys
import time

import httpx


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

_BASE_URL   = lambda: os.environ["BI_API_URL"].rstrip("/")
_HEADERS    = lambda: {"X-Api-Key": os.environ["BI_API_KEY"]}
_TIMEOUT    = 90
_RETRIES    = 3
_RETRY_WAIT = 20


def _warmup() -> None:
    url = f"{_BASE_URL()}/api/ping"
    print(f"  Acordando a API ({url})...")
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, timeout=_TIMEOUT)
            if r.status_code == 200:
                print(f"  API respondeu (tentativa {attempt}).")
                return
        except httpx.TimeoutException:
            pass
        if attempt < _RETRIES:
            print(f"  Aguardando {_RETRY_WAIT}s...")
            time.sleep(_RETRY_WAIT)
    print("  Aviso: API não confirmou ping. Tentando coletar dados mesmo assim.")


def fetch_summary() -> dict:
    url = f"{_BASE_URL()}/api/reports/daily-summary"
    last_exc: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, headers=_HEADERS(), timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < _RETRIES:
                print(f"  Tentativa {attempt} falhou ({type(exc).__name__}) — aguardando {_RETRY_WAIT}s...")
                time.sleep(_RETRY_WAIT)
    raise RuntimeError(f"Falha ao buscar daily-summary após {_RETRIES} tentativas: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Formatação da mensagem
# ---------------------------------------------------------------------------

def format_message(data: dict) -> str:
    """Formata o resumo como texto compacto para WhatsApp."""
    ref      = data.get("data_referencia", "—")
    ativos   = data.get("total_ativos", 0)
    delta    = data.get("delta_dia", 0)
    entradas = data.get("entradas_dia", 0)
    saidas   = data.get("saidas_dia", 0)
    setores  = data.get("setores", [])
    c30      = data.get("criticos_30d", 0)
    c90      = data.get("criticos_90d", 0)

    if delta > 0:
        delta_str = f"▲{delta}"
    elif delta < 0:
        delta_str = f"▼{abs(delta)}"
    else:
        delta_str = "="

    linhas_setores = "\n".join(
        f"{s['setor']}: {s['ativos']} proc | ↑{s['entradas']} ↓{s['saidas']}"
        for s in setores
    )

    criticos_bloco = ""
    if c30 > 0:
        criticos_bloco = (
            f"⚠️ *Atenção*\n"
            f"• +30 dias: {c30}\n"
            f"• +90 dias: {c90}\n\n"
        )

    return (
        f"📊 *BI COPAG — {ref}*\n\n"
        f"*Visão geral*\n"
        f"Ativos: *{ativos:,}* ({delta_str} no dia)\n"
        f"Entradas: {entradas} · Saídas: {saidas}\n\n"
        f"*Por setor*\n"
        f"{linhas_setores}\n\n"
        f"{criticos_bloco}"
        f"🔗 bi-copag.vercel.app"
    )


# ---------------------------------------------------------------------------
# Envio (WhatsApp Cloud API — Meta)
# ---------------------------------------------------------------------------

def send_whatsapp(message: str, recipient: str) -> None:
    """Envia mensagem via WhatsApp Cloud API (Meta).

    Requer WHATSAPP_TOKEN, WHATSAPP_PHONE_ID e um template pré-aprovado.
    O template deve ter o corpo da mensagem como componente de texto livre
    (após aprovação como categoria 'utility').

    Variáveis de template são passadas como parâmetros numerados {{1}}, {{2}}, ...
    Implemente o mapeamento abaixo quando o template for aprovado.
    """
    token    = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_ID"]
    template = os.getenv("WHATSAPP_TEMPLATE", "bi_copag_daily_report")

    # TODO: mapear os campos de `message` para os parâmetros numerados do
    # template aprovado pela Meta quando a aprovação for concluída.
    # Exemplo de payload para template com texto livre:
    # {
    #   "messaging_product": "whatsapp",
    #   "to": recipient,
    #   "type": "template",
    #   "template": {
    #     "name": template,
    #     "language": {"code": "pt_BR"},
    #     "components": [{"type": "body", "parameters": [{"type": "text", "text": message}]}]
    #   }
    # }

    raise NotImplementedError(
        "Envio real ainda não configurado — aguardando aprovação do template Meta. "
        "Execute com --dry-run enquanto o template não for aprovado."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Relatório diário WhatsApp — BI COPAG")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=not bool(os.getenv("WHATSAPP_TOKEN")),
        help="Imprime a mensagem sem enviar (padrão quando WHATSAPP_TOKEN não está configurado)",
    )
    args = parser.parse_args()

    print(f"=== Relatório diário WhatsApp — BI COPAG ({'dry-run' if args.dry_run else 'PRODUÇÃO'}) ===")

    print("Acordando API...")
    _warmup()

    print("Coletando resumo diário...")
    data = fetch_summary()
    print(f"  Referência: {data.get('data_referencia')} | Ativos: {data.get('total_ativos')}")

    print("Formatando mensagem...")
    message = format_message(data)

    if args.dry_run:
        print("\n" + "─" * 50)
        print("MENSAGEM QUE SERIA ENVIADA:")
        print("─" * 50)
        print(message)
        print("─" * 50)
        print("\n✓ Dry-run concluído. Nenhuma mensagem foi enviada.")
        return

    recipients = [n.strip() for n in os.environ["WHATSAPP_RECIPIENTS"].split(",") if n.strip()]
    if not recipients:
        print("✗ WHATSAPP_RECIPIENTS está vazio. Nenhum destinatário configurado.")
        sys.exit(1)

    erros = []
    for recipient in recipients:
        try:
            send_whatsapp(message, recipient)
            print(f"  ✓ Enviado para {recipient}")
        except Exception as exc:
            msg = f"  ✗ Falha ao enviar para {recipient}: {exc}"
            print(msg)
            erros.append(msg)

    if erros:
        print(f"\n✗ {len(erros)} erro(s) de envio.")
        sys.exit(1)
    else:
        print(f"\n✓ Relatório enviado para {len(recipients)} destinatário(s).")


if __name__ == "__main__":
    main()

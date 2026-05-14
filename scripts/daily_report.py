#!/usr/bin/env python3
"""
Relatório diário por e-mail — BI COPAG
=======================================
Coleta o resumo diário do endpoint /api/reports/daily-summary e envia um
e-mail HTML compacto (card de notificação) via Google Workspace.

Disparado automaticamente seg–sex às 19:30 BRT pelo GitHub Actions,
30 min após o upload SEI diário.

Variáveis de ambiente:
    BI_API_URL          URL da API do BI
    BI_API_KEY          API key do BI (mesma que API_UPLOAD_KEY no Render)
    GMAIL_USER          copag@progep.ufc.br
    GMAIL_APP_PASSWORD  Senha de app Google (myaccount.google.com → Senhas de app)
    REPORT_RECIPIENTS   E-mails separados por vírgula
"""

import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

_FONT       = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
_BASE_URL   = lambda: os.environ["BI_API_URL"].rstrip("/")
_HEADERS    = lambda: {"X-Api-Key": os.environ["BI_API_KEY"]}
_TIMEOUT    = 90
_RETRIES    = 3
_RETRY_WAIT = 20


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

def _warmup() -> None:
    url = f"{_BASE_URL()}/api/ping"
    print(f"  Acordando a API ({url})...")
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, timeout=_TIMEOUT)
            if r.status_code == 200:
                print(f"  API respondeu (tentativa {attempt}).")
                return
        except (httpx.TimeoutException, httpx.RequestError):
            pass
        if attempt < _RETRIES:
            print(f"  Aguardando {_RETRY_WAIT}s...")
            time.sleep(_RETRY_WAIT)
    print("  Aviso: API não confirmou ping. Tentando mesmo assim.")


def fetch_summary() -> dict:
    url = f"{_BASE_URL()}/api/reports/daily-summary"
    last_exc: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, headers=_HEADERS(), timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            if attempt < _RETRIES:
                print(f"  Tentativa {attempt} falhou ({type(exc).__name__}) — aguardando {_RETRY_WAIT}s...")
                time.sleep(_RETRY_WAIT)
    raise RuntimeError(f"Falha ao buscar daily-summary após {_RETRIES} tentativas: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# HTML do e-mail
# ---------------------------------------------------------------------------

def _sector_rows(setores: list[dict], total: int) -> str:
    """Linhas de setor com mini-barra proporcional de carga."""
    rows = ""
    for i, s in enumerate(setores):
        pct     = round(s["ativos"] / max(total, 1) * 100)
        bar_w   = max(3, pct)
        bg      = "#fafbff" if i % 2 == 0 else "#ffffff"
        rows += (
            f"<table width='100%' cellpadding='0' cellspacing='0'"
            f" style='margin-bottom:1px;background:{bg};border-radius:6px'>"
            f"<tr>"
            f"<td width='90' style='padding:9px 8px 9px 12px;font-family:{_FONT};"
            f"font-weight:700;font-size:.82rem;color:#273168'>{s['setor']}</td>"
            f"<td style='padding:9px 6px'>"
            f"<table width='100%' cellpadding='0' cellspacing='0'><tr>"
            f"<td width='{bar_w}%' style='background:#273168;height:5px;"
            f"border-radius:99px;opacity:.55'></td>"
            f"<td style='height:5px'></td>"
            f"</tr></table>"
            f"</td>"
            f"<td width='48' style='padding:9px 6px;text-align:right;font-family:{_FONT};"
            f"font-weight:800;font-size:.88rem;color:#1a2050'>{s['ativos']}</td>"
            f"<td width='38' style='padding:9px 4px;text-align:center;font-family:{_FONT};"
            f"font-size:.78rem;color:#1a7a50;font-weight:700'>+{s['entradas']}</td>"
            f"<td width='38' style='padding:9px 12px 9px 4px;text-align:center;"
            f"font-family:{_FONT};font-size:.78rem;color:#d4750e;font-weight:700'>-{s['saidas']}</td>"
            f"</tr></table>"
        )
    return rows


def _criticos_bloco(c30: int, c90: int) -> str:
    if c30 == 0:
        return ""
    c90_line = ""
    if c90 > 0:
        c90_line = (
            f"<div style='margin-top:7px;padding-top:7px;"
            f"border-top:1px solid rgba(183,28,28,.14)'>"
            f"<span style='font-family:{_FONT};font-size:.78rem;color:#b71c1c;font-weight:700'>"
            f"🔴 Situação extrema (+90 dias):&nbsp;</span>"
            f"<span style='font-family:{_FONT};font-size:.85rem;font-weight:800;color:#b71c1c'>"
            f"{c90}</span>"
            f"</div>"
        )
    return (
        f"<div style='background:#fff8f0;border-left:3px solid #f39320;"
        f"border-radius:0 8px 8px 0;padding:12px 16px;margin:14px 0'>"
        f"<div style='font-family:{_FONT};font-size:.72rem;font-weight:700;"
        f"color:#b85e08;text-transform:uppercase;letter-spacing:.08em;"
        f"margin-bottom:5px'>⚠&nbsp; Processos parados</div>"
        f"<div style='font-family:{_FONT};font-size:.82rem;color:#5a6390'>"
        f"Acima de 30 dias: "
        f"<strong style='color:#d4750e;font-size:.92rem'>{c30}</strong>"
        f"</div>"
        f"{c90_line}"
        f"</div>"
    )


def _delta_style(delta: int) -> tuple[str, str, str]:
    """Retorna (cor, seta+valor, rótulo) baseado no saldo do dia."""
    if delta < 0:
        return "#1a7a50", f"▼{abs(delta)}", "Redução"
    if delta > 0:
        return "#d4750e", f"▲{delta}", "Acúmulo"
    return "#5a6390", "=", "Equilíbrio"


def build_html(data: dict) -> str:
    ref      = data.get("data_referencia", "—")
    ativos   = data.get("total_ativos", 0)
    delta    = data.get("delta_dia", 0)
    entradas = data.get("entradas_dia", 0)
    saidas   = data.get("saidas_dia", 0)
    setores  = data.get("setores", [])
    c30      = data.get("criticos_30d", 0)
    c90      = data.get("criticos_90d", 0)

    delta_cor, delta_str, delta_label = _delta_style(delta)
    total_setor = max(sum(s["ativos"] for s in setores), 1)
    setor_rows  = _sector_rows(setores, total_setor)
    criticos    = _criticos_bloco(c30, c90)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:20px 0;background:#d8dbe8;font-family:{_FONT};color:#1a2050">

  <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:10px;
              overflow:hidden;box-shadow:0 8px 32px rgba(39,49,104,.20)">

    <!-- Tarja laranja/dourada -->
    <div style="height:3px;background:linear-gradient(90deg,#f39320,#febb12,#f39320)"></div>

    <!-- Cabeçalho — hero com número grande -->
    <div style="background:linear-gradient(160deg,#1a2762 0%,#273168 40%,#0f1a44 100%);
                padding:26px 32px 22px">
      <!-- Badge institucional -->
      <div style="font-family:{_FONT};font-size:.58rem;font-weight:700;letter-spacing:.2em;
                  text-transform:uppercase;color:rgba(254,187,18,.75);margin-bottom:14px">
        SEI BI &nbsp;·&nbsp; COPAG &nbsp;·&nbsp; PROGEP &nbsp;·&nbsp; UFC
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <!-- Número principal -->
          <td style="vertical-align:bottom">
            <div style="font-family:{_FONT};font-size:3rem;font-weight:800;color:#febb12;
                        line-height:1;letter-spacing:-.02em">{ativos:,}</div>
            <div style="font-family:{_FONT};font-size:.65rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:.14em;
                        color:rgba(240,244,255,.45);margin-top:5px">Processos ativos</div>
          </td>
          <!-- Saldo + data -->
          <td style="text-align:right;vertical-align:bottom;padding-bottom:2px">
            <div style="font-family:{_FONT};font-size:.72rem;color:rgba(240,244,255,.4);
                        margin-bottom:8px">{ref}</div>
            <div style="display:inline-block;background:rgba(255,255,255,.08);
                        border:1px solid rgba(255,255,255,.13);border-radius:7px;
                        padding:9px 16px;text-align:center">
              <div style="font-family:{_FONT};font-size:1.4rem;font-weight:800;
                          color:{delta_cor};line-height:1">{delta_str}</div>
              <div style="font-family:{_FONT};font-size:.58rem;font-weight:700;
                          color:rgba(240,244,255,.42);text-transform:uppercase;
                          letter-spacing:.1em;margin-top:3px">{delta_label}</div>
            </div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Faixa de fluxo do dia -->
    <div style="background:#eef0f6;padding:14px 32px">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td width="47%" style="text-align:center;padding:12px 10px;background:#ecfdf5;
                                  border-radius:8px;border:1px solid rgba(26,122,80,.18)">
            <div style="font-family:{_FONT};font-size:.6rem;font-weight:700;color:#1a7a50;
                        text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px">
              ↑ &nbsp;Entradas
            </div>
            <div style="font-family:{_FONT};font-size:1.7rem;font-weight:800;
                        color:#1a7a50;line-height:1">{entradas}</div>
          </td>
          <td width="6%" style="text-align:center">
            <div style="font-family:{_FONT};font-size:.8rem;color:#b0b4c8">→</div>
          </td>
          <td width="47%" style="text-align:center;padding:12px 10px;background:#fff8f0;
                                  border-radius:8px;border:1px solid rgba(243,147,32,.2)">
            <div style="font-family:{_FONT};font-size:.6rem;font-weight:700;color:#d4750e;
                        text-transform:uppercase;letter-spacing:.1em;margin-bottom:5px">
              ↓ &nbsp;Saídas
            </div>
            <div style="font-family:{_FONT};font-size:1.7rem;font-weight:800;
                        color:#d4750e;line-height:1">{saidas}</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Corpo -->
    <div style="padding:18px 32px 24px;background:#ffffff">

      <!-- Label seção -->
      <div style="font-family:{_FONT};font-size:.6rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:.14em;color:#9a9fc0;margin-bottom:10px;padding-bottom:8px;
                  border-bottom:1px solid #eef0f8">Por setor</div>

      <!-- Linhas de setor com barra proporcional -->
      {setor_rows}

      {criticos}

      <!-- CTA -->
      <div style="text-align:center;padding-top:16px;margin-top:10px;
                  border-top:1px solid #eef0f8">
        <a href="https://bi-copag.vercel.app"
           style="display:inline-block;background:linear-gradient(135deg,#273168,#1c2350);
                  color:#ffffff;text-decoration:none;padding:11px 32px;border-radius:6px;
                  font-family:{_FONT};font-size:.85rem;font-weight:700;letter-spacing:.02em">
          Abrir plataforma →
        </a>
        <div style="font-family:{_FONT};font-size:.68rem;color:#bbb;margin-top:9px">
          bi-copag.vercel.app &nbsp;·&nbsp; Gerado automaticamente às 19:30 BRT
        </div>
      </div>

    </div>

    <!-- Tarja inferior -->
    <div style="height:3px;background:linear-gradient(90deg,#273168,#3d4fa0,#273168)"></div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------

def send_email(html: str, ref: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    recipients = os.environ["REPORT_RECIPIENTS"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 BI COPAG — {ref}"
    msg["From"]    = gmail_user
    msg["To"]      = recipients
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_user, gmail_pass)
        smtp.send_message(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Relatório diário BI COPAG ===")

    print("Acordando API...")
    _warmup()

    print("Coletando resumo diário...")
    data = fetch_summary()
    ref = data.get("data_referencia", "—")
    print(f"  Referência: {ref} | Ativos: {data.get('total_ativos')} | "
          f"Entradas: {data.get('entradas_dia')} | Saídas: {data.get('saidas_dia')}")

    print("Gerando HTML...")
    html = build_html(data)

    print("Enviando e-mail...")
    send_email(html, ref)

    print(f"✓ Relatório diário enviado para: {os.environ['REPORT_RECIPIENTS']}")

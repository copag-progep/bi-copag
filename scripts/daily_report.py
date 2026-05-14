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

def _sector_rows(setores: list[dict]) -> str:
    rows = ""
    for i, s in enumerate(setores):
        bg = "#fafbff" if i % 2 == 0 else "#ffffff"
        rows += (
            f"<tr style='background:{bg}'>"
            f"<td style='padding:8px 12px;font-family:{_FONT};font-weight:700;"
            f"font-size:.85rem;color:#273168'>{s['setor']}</td>"
            f"<td style='padding:8px 12px;text-align:right;font-family:{_FONT};"
            f"font-weight:800;font-size:.9rem;color:#1a2050'>{s['ativos']}</td>"
            f"<td style='padding:8px 12px;text-align:center;font-family:{_FONT};"
            f"font-size:.82rem;color:#1a7a50;font-weight:600'>+{s['entradas']}</td>"
            f"<td style='padding:8px 12px;text-align:center;font-family:{_FONT};"
            f"font-size:.82rem;color:#d4750e;font-weight:600'>-{s['saidas']}</td>"
            f"</tr>"
        )
    return rows


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

    setor_rows = _sector_rows(setores)

    criticos_bloco = ""
    if c30 > 0:
        criticos_bloco = f"""
      <div style="background:#fff8f0;border-left:3px solid #f39320;padding:12px 16px;
                  border-radius:0 8px 8px 0;margin-bottom:16px">
        <div style="font-family:{_FONT};font-weight:700;color:#d4750e;
                    font-size:.85rem;margin-bottom:3px">⚠ Processos parados</div>
        <div style="font-family:{_FONT};font-size:.8rem;color:#5a6390">
          Acima de 30 dias: <strong style="color:#d4750e">{c30}</strong>
          &nbsp;·&nbsp;
          Acima de 90 dias: <strong style="color:#bf3535">{c90}</strong>
        </div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:16px 0;background:#dde0ea;font-family:{_FONT};color:#1a2050">

  <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:8px;
              overflow:hidden;box-shadow:0 4px 20px rgba(39,49,104,.16)">

    <!-- Tarja superior -->
    <div style="height:3px;background:linear-gradient(90deg,#f39320,#febb12)"></div>

    <!-- Cabeçalho -->
    <div style="background:linear-gradient(135deg,#273168 0%,#1c2350 55%,#111840 100%);
                padding:18px 28px">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="vertical-align:middle">
            <div style="font-family:{_FONT};font-size:.62rem;font-weight:700;
                        letter-spacing:.18em;text-transform:uppercase;
                        color:rgba(254,187,18,.85);margin-bottom:4px">
              SEI BI &nbsp;·&nbsp; COPAG &nbsp;·&nbsp; PROGEP &nbsp;·&nbsp; UFC
            </div>
            <div style="font-family:{_FONT};font-size:1.1rem;font-weight:800;
                        color:#ffffff;line-height:1.1">
              Relatório Diário &nbsp;·&nbsp;
              <span style="color:rgba(254,187,18,.9)">{ref}</span>
            </div>
          </td>
          <td style="text-align:right;vertical-align:middle;white-space:nowrap">
            <div style="display:inline-block;background:rgba(243,147,32,.18);
                        border:1px solid rgba(243,147,32,.30);border-radius:8px;
                        padding:8px 14px;text-align:center">
              <div style="font-family:{_FONT};font-size:1.4rem;font-weight:800;
                           color:#febb12;line-height:1">{ativos:,}</div>
              <div style="font-family:{_FONT};font-size:.58rem;font-weight:700;
                           color:rgba(240,244,255,.50);text-transform:uppercase;
                           letter-spacing:.12em;margin-top:2px">ativos</div>
            </div>
          </td>
        </tr>
      </table>
    </div>
    <div style="height:2px;background:linear-gradient(90deg,#273168,#3d4fa0)"></div>

    <!-- Corpo -->
    <div style="padding:20px 28px;background:#f8f9fd">

      <!-- KPIs do dia -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px">
        <tr>
          <td width="33%" style="padding-right:6px">
            <div style="background:#ffffff;border-radius:8px;padding:12px 10px;
                        text-align:center;border-top:2px solid {delta_cor}">
              <div style="font-family:{_FONT};font-size:1.3rem;font-weight:800;
                          color:{delta_cor};line-height:1">{delta_str}</div>
              <div style="font-family:{_FONT};font-size:.62rem;color:#5a6390;
                          text-transform:uppercase;letter-spacing:.08em;
                          margin-top:4px">{delta_label}</div>
            </div>
          </td>
          <td width="33%" style="padding:0 3px">
            <div style="background:#f0faf5;border-radius:8px;padding:12px 10px;
                        text-align:center;border-top:2px solid #1a7a50">
              <div style="font-family:{_FONT};font-size:1.3rem;font-weight:800;
                          color:#1a7a50;line-height:1">{entradas}</div>
              <div style="font-family:{_FONT};font-size:.62rem;color:#5a6390;
                          text-transform:uppercase;letter-spacing:.08em;
                          margin-top:4px">Entradas</div>
            </div>
          </td>
          <td width="33%" style="padding-left:6px">
            <div style="background:#fff8f0;border-radius:8px;padding:12px 10px;
                        text-align:center;border-top:2px solid #f39320">
              <div style="font-family:{_FONT};font-size:1.3rem;font-weight:800;
                          color:#d4750e;line-height:1">{saidas}</div>
              <div style="font-family:{_FONT};font-size:.62rem;color:#5a6390;
                          text-transform:uppercase;letter-spacing:.08em;
                          margin-top:4px">Saídas</div>
            </div>
          </td>
        </tr>
      </table>

      <!-- Tabela de setores -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;
             border-radius:8px;border:1px solid #e8eaf0;border-collapse:collapse;overflow:hidden">
        <thead>
          <tr style="background:#f5f6fb">
            <th style="padding:7px 12px;text-align:left;font-family:{_FONT};font-size:.62rem;
                       color:#5a6390;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Setor</th>
            <th style="padding:7px 12px;text-align:right;font-family:{_FONT};font-size:.62rem;
                       color:#5a6390;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Ativos</th>
            <th style="padding:7px 12px;text-align:center;font-family:{_FONT};font-size:.62rem;
                       color:#1a7a50;text-transform:uppercase;letter-spacing:.08em;font-weight:700">↑ Ent.</th>
            <th style="padding:7px 12px;text-align:center;font-family:{_FONT};font-size:.62rem;
                       color:#d4750e;text-transform:uppercase;letter-spacing:.08em;font-weight:700">↓ Saí.</th>
          </tr>
        </thead>
        <tbody>{setor_rows}</tbody>
      </table>

      {criticos_bloco}

      <!-- Botão e rodapé -->
      <div style="text-align:center;padding-top:4px">
        <a href="https://bi-copag.vercel.app"
           style="display:inline-block;background:linear-gradient(135deg,#273168,#1c2350);
                  color:#ffffff;text-decoration:none;padding:11px 28px;border-radius:6px;
                  font-family:{_FONT};font-size:.85rem;font-weight:700">
          Abrir plataforma →
        </a>
        <div style="font-family:{_FONT};font-size:.7rem;color:#aaa;margin-top:10px">
          Gerado automaticamente &nbsp;·&nbsp; BI COPAG &nbsp;·&nbsp;
          <a href="https://bi-copag.vercel.app" style="color:#273168;font-weight:600;
             text-decoration:none">bi-copag.vercel.app</a>
        </div>
      </div>

    </div>

    <!-- Tarja inferior -->
    <div style="height:2px;background:linear-gradient(90deg,#273168,#3d4fa0)"></div>

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

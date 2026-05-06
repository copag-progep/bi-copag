#!/usr/bin/env python3
"""
Alertas automáticos de processos críticos — BI COPAG
=====================================================
Consulta a API do BI e envia e-mail quando há processos sem movimentação
há 30+ dias. O e-mail inclui o resumo por faixa e a lista dos mais críticos.

Não envia e-mail se não houver processos com mais de 30 dias.

Variáveis de ambiente necessárias:
    BI_API_URL          URL da API do BI
    BI_API_KEY          API key
    GMAIL_USER          copag@progep.ufc.br
    GMAIL_APP_PASSWORD  Senha de app Google
    REPORT_RECIPIENTS   E-mails separados por vírgula
"""

import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx


def fetch(path: str) -> dict:
    r = httpx.get(
        f"{os.environ['BI_API_URL']}{path}",
        headers={"X-Api-Key": os.environ["BI_API_KEY"]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def flag_color(dias: int) -> str:
    if dias >= 90: return "#4a148c"
    if dias >= 60: return "#b71c1c"
    if dias >= 45: return "#c0392b"
    return "#d4750e"


def flag_label(dias: int) -> str:
    if dias >= 90: return "90d+"
    if dias >= 60: return "60–89d"
    if dias >= 45: return "45–59d"
    return "30–44d"


def build_html(summary: dict) -> str | None:
    mais_30 = summary.get("mais_de_30", 0)
    if mais_30 == 0:
        return None   # sem alertas — não envia e-mail

    mais_45 = summary.get("mais_de_45", 0)
    mais_90 = summary.get("mais_de_90", 0)
    criticos = summary.get("criticos", [])
    ref      = summary.get("data_referencia", "")
    hoje     = date.today().strftime("%d/%m/%Y")

    rows = ""
    for p in criticos:
        dias  = p.get("dias_sem_movimentacao", 0)
        cor   = flag_color(dias)
        label = flag_label(dias)
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e8eaf0;
                     font-family:monospace;font-size:.8rem">{p.get("protocolo", "")}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e8eaf0">{p.get("setor", "")}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e8eaf0">{p.get("atribuicao") or "—"}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e8eaf0;text-align:center">
            <span style="background:{cor}18;color:{cor};padding:2px 8px;
                         border-radius:999px;font-weight:700;font-size:.78rem">{dias}d — {label}</span>
          </td>
        </tr>"""

    aviso_90 = ""
    if mais_90 > 0:
        aviso_90 = f"""
        <div style="background:rgba(74,20,140,.08);border-left:4px solid #4a148c;
                    padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:16px">
          <strong style="color:#4a148c">⚠️ Situação extrema: {mais_90} processo(s) acima de 90 dias</strong>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;color:#1a2050;max-width:700px;margin:0 auto">

  <!-- Cabeçalho -->
  <div style="background:linear-gradient(140deg,#273168,#1c2350);
              padding:28px 32px;border-radius:12px 12px 0 0">
    <h1 style="margin:0;color:#fff;font-size:1.35rem">
      ⚠️ Alerta — Processos sem movimentação
    </h1>
    <p style="color:rgba(240,244,255,.7);margin:8px 0 0;font-size:.875rem">
      Referência: {ref} &nbsp;·&nbsp; Gerado em {hoje}
    </p>
  </div>
  <div style="height:3px;background:linear-gradient(90deg,#f39320,#febb12)"></div>

  <!-- Corpo -->
  <div style="padding:24px;background:#f4f5f9">

    <!-- Cards de resumo -->
    <table width="100%" cellpadding="14" style="background:white;border-radius:8px;
                                                margin-bottom:20px;border:1px solid #e8eaf0">
      <tr>
        <td style="text-align:center;border-right:1px solid #e8eaf0">
          <strong style="color:#d4750e;font-size:1.6rem">{mais_30}</strong>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                      letter-spacing:.06em;margin-top:4px">Processos &gt;30d</div>
        </td>
        <td style="text-align:center;border-right:1px solid #e8eaf0">
          <strong style="color:#b71c1c;font-size:1.6rem">{mais_45}</strong>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                      letter-spacing:.06em;margin-top:4px">Processos &gt;45d</div>
        </td>
        <td style="text-align:center">
          <strong style="color:#4a148c;font-size:1.6rem">{mais_90}</strong>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                      letter-spacing:.06em;margin-top:4px">Processos &gt;90d</div>
        </td>
      </tr>
    </table>

    {aviso_90}

    <!-- Tabela de processos críticos -->
    <h3 style="color:#273168;margin:0 0 10px">Processos mais críticos (≥45 dias)</h3>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:white;border-radius:8px;border:1px solid #e8eaf0;
                  border-collapse:collapse">
      <thead>
        <tr style="background:#f5f6fb">
          <th style="padding:8px 12px;text-align:left;font-size:.7rem;
                     color:#5a6390;text-transform:uppercase">Protocolo</th>
          <th style="padding:8px 12px;text-align:left;font-size:.7rem;
                     color:#5a6390;text-transform:uppercase">Setor</th>
          <th style="padding:8px 12px;text-align:left;font-size:.7rem;
                     color:#5a6390;text-transform:uppercase">Atribuição</th>
          <th style="padding:8px 12px;text-align:center;font-size:.7rem;
                     color:#5a6390;text-transform:uppercase">Dias</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <!-- Link para o BI -->
    <p style="text-align:center;margin-top:18px">
      <a href="https://bi-copag.vercel.app/atribuicoes"
         style="background:#273168;color:#fff;padding:10px 22px;
                border-radius:8px;text-decoration:none;font-weight:700;
                font-size:.875rem">
        Ver relatório completo no BI COPAG →
      </a>
    </p>

    <p style="color:#aaa;font-size:.72rem;text-align:center;margin-top:16px">
      Alerta gerado automaticamente pelo BI COPAG ·
      <a href="https://bi-copag.vercel.app" style="color:#273168">bi-copag.vercel.app</a>
    </p>
  </div>
</body></html>"""


def send_email(html: str, mais_30: int) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"⚠️ BI COPAG — {date.today().strftime('%d/%m/%Y')}"
        f" — {mais_30} processo(s) sem movimentação há 30+ dias"
    )
    msg["From"] = gmail_user
    msg["To"]   = os.environ["REPORT_RECIPIENTS"]
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_user, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)


if __name__ == "__main__":
    print("Consultando alertas no BI COPAG...")
    summary = fetch("/api/alerts/summary")

    mais_30 = summary.get("mais_de_30", 0)
    mais_45 = summary.get("mais_de_45", 0)
    mais_90 = summary.get("mais_de_90", 0)

    print(f"  >30d: {mais_30}  |  >45d: {mais_45}  |  >90d: {mais_90}")

    html = build_html(summary)
    if html is None:
        print("✓ Nenhum processo com mais de 30 dias — e-mail não enviado.")
        sys.exit(0)

    send_email(html, mais_30)
    print(f"✓ Alerta enviado para: {os.environ['REPORT_RECIPIENTS']}")

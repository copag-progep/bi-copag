#!/usr/bin/env python3
"""
Relatório gerencial semanal — BI COPAG
=======================================
Coleta dados da API do BI via API key, gera um e-mail HTML com os
principais indicadores da semana e envia via Google Workspace (smtp.gmail.com).

Disparado automaticamente toda sexta-feira pelo GitHub Actions.
Pode ser disparado manualmente em qualquer momento via workflow_dispatch.

Variáveis de ambiente necessárias:
    BI_API_URL          URL da API do BI
    BI_API_KEY          API key (mesma configurada no Render como API_UPLOAD_KEY)
    GMAIL_USER          copag@progep.ufc.br
    GMAIL_APP_PASSWORD  Senha de app Google (myaccount.google.com → Segurança → Senhas de app)
    REPORT_RECIPIENTS   E-mails separados por vírgula (ex: coord@ufc.br,diretor@ufc.br)
"""

import os
import smtplib
import time
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx


# ---------------------------------------------------------------------------
# Coleta de dados da API do BI
# ---------------------------------------------------------------------------

_BASE_URL   = lambda: os.environ["BI_API_URL"]
_HEADERS    = lambda: {"X-Api-Key": os.environ["BI_API_KEY"]}
_TIMEOUT    = 120   # segundos por tentativa
_RETRIES    = 3
_RETRY_WAIT = 30    # segundos entre tentativas


def _warmup() -> None:
    """Faz um ping leve no health check para acordar o Render antes de buscar dados."""
    url = f"{_BASE_URL()}/api/health"
    print(f"  Aquecendo a API ({url})...")
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, timeout=_TIMEOUT)
            if r.status_code == 200:
                print(f"  API respondeu (tentativa {attempt}).")
                return
        except httpx.TimeoutException:
            pass
        if attempt < _RETRIES:
            print(f"  API não respondeu — aguardando {_RETRY_WAIT}s antes de tentar novamente...")
            time.sleep(_RETRY_WAIT)
    print("  Aviso: API não confirmou health check. Tentando coletar dados mesmo assim.")


def fetch(path: str, **params) -> dict:
    """Chama um endpoint analítico do BI usando API key, com retry automático."""
    url = f"{_BASE_URL()}{path}"
    last_exc: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            r = httpx.get(url, params=params, headers=_HEADERS(), timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < _RETRIES:
                print(f"  Tentativa {attempt} falhou ({type(exc).__name__}) — aguardando {_RETRY_WAIT}s...")
                time.sleep(_RETRY_WAIT)
    raise RuntimeError(f"Falha ao buscar {path} após {_RETRIES} tentativas: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Geração do HTML do relatório
# ---------------------------------------------------------------------------

def _cor_flag(dias: int) -> str:
    if dias >= 90: return "#4a148c"
    if dias >= 60: return "#b71c1c"
    if dias >= 45: return "#c0392b"
    if dias >= 30: return "#d4750e"
    if dias >= 15: return "#9a6c00"
    return "#1a7a50"


def _faixa_label(dias: int) -> str:
    if dias >= 90: return "90d+"
    if dias >= 60: return "60–89d"
    if dias >= 45: return "45–59d"
    if dias >= 30: return "30–44d"
    if dias >= 15: return "15–29d"
    return "<15d"


def build_html(dashboard: dict, balance: dict, stale: dict) -> str:
    kpis       = dashboard.get("kpis", {})
    setores    = dashboard.get("por_setor", [])
    servidores = balance.get("servidores", [])
    stats_bal  = balance.get("stats", {})
    contagens  = stale.get("contagens", {})
    criticos   = stale.get("processos", [])[:5]   # top 5 mais antigos
    sobrecarga = [s for s in servidores if s.get("status") == "sobrecarga"]
    hoje_str   = date.today().strftime("%d/%m/%Y")
    semana_ant = (date.today() - timedelta(days=7)).strftime("%d/%m/%Y")
    ref        = dashboard.get("data_referencia", "")

    # Colunas de distribuição por setor
    setor_rows = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e8eaf0'>{s['label']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e8eaf0;text-align:right;font-weight:700'>{s['value']}</td></tr>"
        for s in setores
    )

    # Servidores em sobrecarga
    sobrecarga_html = ""
    if sobrecarga:
        def _delta_tag(s: dict) -> str:
            if s.get("delta") and s["delta"] > 0:
                return f'  <span style="color:#bf3535">▲{abs(s["delta"])}</span>'
            return ""

        itens = "".join(
            f"<li style='margin:4px 0'><strong>{s['atribuicao']}</strong> "
            f"— {s['carga']} processos ({s['pct_total']}% do total)"
            f"{_delta_tag(s)}"
            f"</li>"
            for s in sobrecarga
        )
        sobrecarga_html = f"""
        <div style="background:#fff3f3;border-left:4px solid #bf3535;padding:16px;border-radius:0 8px 8px 0;margin:20px 0">
          <strong style="color:#bf3535">⚠️ {len(sobrecarga)} servidor(es) em sobrecarga</strong>
          <ul style="margin:8px 0 0;padding-left:20px;color:#333">{itens}</ul>
        </div>"""

    # Processos críticos (top 5)
    criticos_html = ""
    if criticos:
        def _critical_row(p: dict) -> str:
            dias = p.get("dias_sem_movimentacao", 0)
            cor  = _cor_flag(dias)
            return (
                f"<tr>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #e8eaf0;"
                f"font-family:monospace;font-size:.85rem'>{p.get('protocolo','')}</td>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #e8eaf0'>{p.get('setor','')}</td>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #e8eaf0'>{p.get('atribuicao') or '—'}</td>"
                f"<td style='padding:6px 10px;border-bottom:1px solid #e8eaf0;text-align:center'>"
                f"<span style='background:{cor}22;color:{cor};padding:2px 8px;"
                f"border-radius:999px;font-weight:700;font-size:.8rem'>{dias}d</span></td>"
                f"</tr>"
            )

        rows = "".join(_critical_row(p) for p in criticos)
        criticos_html = f"""
        <h3 style="color:#273168;margin:24px 0 10px">Processos mais antigos sem movimentação</h3>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:white;border-radius:8px;border:1px solid #e8eaf0;border-collapse:collapse">
          <thead>
            <tr style="background:#f5f6fb">
              <th style="padding:8px 10px;text-align:left;font-size:.75rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Protocolo</th>
              <th style="padding:8px 10px;text-align:left;font-size:.75rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Setor</th>
              <th style="padding:8px 10px;text-align:left;font-size:.75rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Atribuição</th>
              <th style="padding:8px 10px;text-align:center;font-size:.75rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Dias</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    delta_total = stats_bal.get("delta_total")
    delta_str   = (f" <span style='color:{'#bf3535' if delta_total and delta_total > 0 else '#1a7a50'}'>"
                   f"({'▲' if delta_total and delta_total > 0 else '▼'}{abs(delta_total or 0)} vs semana ant.)</span>"
                   if delta_total is not None else "")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#eef0f8;font-family:Arial,sans-serif;color:#1a2050">
<div style="max-width:680px;margin:24px auto;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(39,49,104,.15)">

  <!-- Cabeçalho -->
  <div style="background:linear-gradient(140deg,#273168,#1c2350,#111840);padding:32px 36px;position:relative;overflow:hidden">
    <div style="position:absolute;top:-30px;right:-30px;width:140px;height:140px;border-radius:50%;background:rgba(243,147,32,.12)"></div>
    <p style="margin:0 0 4px;font-size:.7rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:rgba(254,187,18,.85)">
      SEI BI · COPAG · UFC
    </p>
    <h1 style="margin:0 0 8px;font-size:1.6rem;font-weight:800;color:#fff">📊 Relatório semanal</h1>
    <p style="margin:0;color:rgba(240,244,255,.7);font-size:.9rem">
      Semana de {semana_ant} a {hoje_str} &nbsp;·&nbsp; Referência: {ref}
    </p>
  </div>
  <div style="height:3px;background:linear-gradient(90deg,#f39320,#febb12)"></div>

  <!-- Corpo -->
  <div style="background:#f4f5f9;padding:28px 36px">

    <!-- KPIs principais -->
    <h3 style="color:#273168;margin:0 0 14px;font-size:1rem">Visão geral</h3>
    <table width="100%" cellpadding="0" cellspacing="12">
      <tr>
        <td width="25%" style="background:white;padding:16px;border-radius:10px;border-left:4px solid #f39320;text-align:center">
          <div style="font-size:1.8rem;font-weight:800;color:#1a2050">{kpis.get('total_processos_ativos',0)}{delta_str}</div>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;letter-spacing:.07em;margin-top:4px">Processos ativos</div>
        </td>
        <td width="25%" style="background:white;padding:16px;border-radius:10px;border-left:4px solid #273168;text-align:center">
          <div style="font-size:1.8rem;font-weight:800;color:#1a2050">{stats_bal.get('total_servidores',0)}</div>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;letter-spacing:.07em;margin-top:4px">Servidores</div>
        </td>
        <td width="25%" style="background:white;padding:16px;border-radius:10px;border-left:4px solid #d4750e;text-align:center">
          <div style="font-size:1.8rem;font-weight:800;color:#d4750e">{contagens.get('mais_de_30',0)}</div>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;letter-spacing:.07em;margin-top:4px">Processos &gt;30 dias</div>
        </td>
        <td width="25%" style="background:white;padding:16px;border-radius:10px;border-left:4px solid #bf3535;text-align:center">
          <div style="font-size:1.8rem;font-weight:800;color:#bf3535">{contagens.get('mais_de_45',contagens.get('mais_de_30',0))}</div>
          <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;letter-spacing:.07em;margin-top:4px">Processos &gt;45 dias</div>
        </td>
      </tr>
    </table>

    {sobrecarga_html}
    {criticos_html}

    <!-- Distribuição por setor -->
    {'<h3 style="color:#273168;margin:24px 0 10px">Distribuição por setor</h3><table width="100%" cellpadding="0" cellspacing="0" style="background:white;border-radius:8px;border:1px solid #e8eaf0;border-collapse:collapse"><tbody>' + setor_rows + '</tbody></table>' if setor_rows else ''}

    <!-- Rodapé -->
    <p style="margin:28px 0 0;color:#888;font-size:.78rem;text-align:center">
      Gerado automaticamente pelo BI COPAG &nbsp;·&nbsp;
      <a href="https://bi-copag.vercel.app" style="color:#273168;font-weight:700">bi-copag.vercel.app</a>
    </p>
  </div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Envio do e-mail
# ---------------------------------------------------------------------------

def send_email(html: str) -> None:
    """Envia o relatório HTML via Google Workspace (smtp.gmail.com:465)."""
    gmail_user = os.environ["GMAIL_USER"]            # copag@progep.ufc.br
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    recipients = os.environ["REPORT_RECIPIENTS"]     # e-mails separados por vírgula

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 BI COPAG — Relatório semanal {date.today().strftime('%d/%m/%Y')}"
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
    print("Coletando dados do BI COPAG...")
    _warmup()
    dashboard = fetch("/api/analytics/dashboard")
    balance   = fetch("/api/analytics/workload-balance")
    stale     = fetch("/api/analytics/stale")

    print("Gerando HTML do relatório...")
    html = build_html(dashboard, balance, stale)

    print("Enviando e-mail...")
    send_email(html)

    print(f"✓ Relatório semanal enviado para: {os.environ['REPORT_RECIPIENTS']}")

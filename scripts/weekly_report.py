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


def fetch_weekly_flow(report_date: date) -> dict:
    """
    Retorna totais de entradas e saídas para a semana do relatório e a semana anterior,
    usando evolucao_fluxo do endpoint entries-exits.

    Inclui a sexta-feira da semana anterior como baseline para que a segunda-feira
    da semana passada tenha uma comparação correta.
    """
    this_mon  = report_date - timedelta(days=report_date.weekday())
    prev_mon  = this_mon - timedelta(weeks=1)
    baseline  = prev_mon - timedelta(days=3)   # sexta antes da semana passada

    flow_data = fetch(
        "/api/analytics/entries-exits",
        data_inicial=baseline.isoformat(),
        data_final=report_date.isoformat(),
    )

    series = flow_data.get("evolucao_fluxo", [])

    # Conjuntos de datas de cada semana (seg–sex)
    this_week = {str(this_mon + timedelta(days=i)) for i in range(5)}
    prev_week = {str(prev_mon  + timedelta(days=i)) for i in range(5)}

    def _sum(dates: set) -> tuple[int, int]:
        ent = sum(item["entradas"] for item in series if item["date"] in dates)
        sai = sum(item["saidas"]   for item in series if item["date"] in dates)
        return ent, sai

    this_e, this_s = _sum(this_week)
    prev_e, prev_s = _sum(prev_week)

    return {
        "this_entradas": this_e,
        "this_saidas":   this_s,
        "prev_entradas": prev_e,
        "prev_saidas":   prev_s,
        "semana_ini":     this_mon.strftime("%d/%m"),
        "semana_fim":     report_date.strftime("%d/%m"),
        "semana_ant_ini": prev_mon.strftime("%d/%m"),
        "semana_ant_fim": (this_mon - timedelta(days=1)).strftime("%d/%m"),
    }


# ---------------------------------------------------------------------------
# Geração do HTML do relatório — formato A4
# ---------------------------------------------------------------------------

def _cor_flag(dias: int) -> str:
    if dias >= 90: return "#4a148c"
    if dias >= 60: return "#b71c1c"
    if dias >= 45: return "#c0392b"
    if dias >= 30: return "#d4750e"
    if dias >= 15: return "#9a6c00"
    return "#1a7a50"


def _delta_html(atual: int, anterior: int, lower_is_better: bool = False) -> str:
    """Retorna um span colorido mostrando a variação em relação à semana anterior."""
    if anterior == 0:
        return ""
    diff = atual - anterior
    if diff == 0:
        return "<span style='color:#5a6390;font-size:.8rem'> = igual à semana ant.</span>"
    positivo = diff > 0
    # Para "entradas" e "saídas": mais é neutro; para criteriosos pode mudar.
    # lower_is_better=True inverte a cor (ex: processos críticos: menos é melhor).
    cor_up   = "#bf3535" if lower_is_better else "#1a7a50"
    cor_down = "#1a7a50" if lower_is_better else "#bf3535"
    cor  = cor_up if positivo else cor_down
    seta = "▲" if positivo else "▼"
    return f"<span style='color:{cor};font-size:.82rem;font-weight:700'> {seta} {abs(diff):+d} vs sem. ant.</span>"


def build_html(dashboard: dict, balance: dict, stale: dict, flow: dict) -> str:
    kpis       = dashboard.get("kpis", {})
    setores    = dashboard.get("por_setor", [])
    servidores = balance.get("servidores", [])
    stats_bal  = balance.get("stats", {})
    contagens  = stale.get("contagens", {})
    criticos   = stale.get("processos", [])[:5]
    sobrecarga = [s for s in servidores if s.get("status") == "sobrecarga"]

    hoje_str   = date.today().strftime("%d/%m/%Y")
    ref        = dashboard.get("data_referencia", "")

    delta_total = stats_bal.get("delta_total")
    delta_str   = ""
    if delta_total is not None:
        cor  = "#bf3535" if delta_total > 0 else "#1a7a50"
        seta = "▲" if delta_total > 0 else "▼"
        delta_str = f"<br><span style='font-size:.8rem;color:{cor};font-weight:700'>{seta} {abs(delta_total)} vs semana ant.</span>"

    # ── Fluxo da semana ──────────────────────────────────────────────
    this_e = flow.get("this_entradas", 0)
    this_s = flow.get("this_saidas",   0)
    prev_e = flow.get("prev_entradas", 0)
    prev_s = flow.get("prev_saidas",   0)
    sem_ini = flow.get("semana_ini", "")
    sem_fim = flow.get("semana_fim", "")

    flow_section = f"""
    <div style="margin:24px 0">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#f39320;border-radius:2px;flex-shrink:0"></div>
        <h2 style="margin:0;font-size:.95rem;font-weight:800;color:#273168;text-transform:uppercase;
                   letter-spacing:.06em">Fluxo da semana ({sem_ini} – {sem_fim})</h2>
      </div>
      <table width="100%" cellpadding="0" cellspacing="10">
        <tr>
          <td width="50%" style="background:#f0faf5;padding:18px 20px;border-radius:10px;
                                  border-left:4px solid #1a7a50">
            <div style="font-size:2rem;font-weight:800;color:#1a7a50">{this_e}
              {_delta_html(this_e, prev_e)}</div>
            <div style="font-size:.72rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Processos que entraram</div>
            <div style="font-size:.75rem;color:#888;margin-top:2px">
              Semana anterior: {prev_e} entradas</div>
          </td>
          <td width="50%" style="background:#fff8f0;padding:18px 20px;border-radius:10px;
                                  border-left:4px solid #f39320">
            <div style="font-size:2rem;font-weight:800;color:#d4750e">{this_s}
              {_delta_html(this_s, prev_s)}</div>
            <div style="font-size:.72rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Processos que saíram</div>
            <div style="font-size:.75rem;color:#888;margin-top:2px">
              Semana anterior: {prev_s} saídas</div>
          </td>
        </tr>
      </table>
    </div>"""

    # ── Distribuição por setor ────────────────────────────────────────
    setor_rows = "".join(
        f"<tr>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eef0f8'>{s['label']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eef0f8;text-align:right;"
        f"font-weight:700;color:#273168'>{s['value']}</td>"
        f"</tr>"
        for s in setores
    )
    setor_section = ""
    if setor_rows:
        setor_section = f"""
    <div style="margin:24px 0">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#f39320;border-radius:2px;flex-shrink:0"></div>
        <h2 style="margin:0;font-size:.95rem;font-weight:800;color:#273168;text-transform:uppercase;
                   letter-spacing:.06em">Distribuição por setor</h2>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:white;border-radius:8px;border:1px solid #e8eaf0;border-collapse:collapse">
        <thead>
          <tr style="background:#f5f6fb">
            <th style="padding:8px 12px;text-align:left;font-size:.72rem;color:#5a6390;
                       text-transform:uppercase;letter-spacing:.07em">Setor</th>
            <th style="padding:8px 12px;text-align:right;font-size:.72rem;color:#5a6390;
                       text-transform:uppercase;letter-spacing:.07em">Processos</th>
          </tr>
        </thead>
        <tbody>{setor_rows}</tbody>
      </table>
    </div>"""

    # ── Sobrecarga ────────────────────────────────────────────────────
    sobrecarga_section = ""
    if sobrecarga:
        def _delta_tag(s: dict) -> str:
            if s.get("delta") and s["delta"] > 0:
                return f' <span style="color:#bf3535;font-weight:700">▲{abs(s["delta"])}</span>'
            return ""
        itens = "".join(
            f"<li style='margin:4px 0'><strong>{s['atribuicao']}</strong> "
            f"— {s['carga']} processos ({s['pct_total']}% do total){_delta_tag(s)}</li>"
            for s in sobrecarga
        )
        sobrecarga_section = f"""
    <div style="background:#fff3f3;border-left:4px solid #bf3535;padding:16px 20px;
                border-radius:0 8px 8px 0;margin:20px 0">
      <strong style="color:#bf3535">⚠ {len(sobrecarga)} servidor(es) em sobrecarga</strong>
      <ul style="margin:8px 0 0;padding-left:20px;color:#333">{itens}</ul>
    </div>"""

    # ── Processos críticos ────────────────────────────────────────────
    criticos_section = ""
    if criticos:
        def _critical_row(p: dict) -> str:
            dias = p.get("dias_sem_movimentacao", 0)
            cor  = _cor_flag(dias)
            return (
                f"<tr>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #eef0f8;"
                f"font-family:monospace;font-size:.82rem'>{p.get('protocolo','')}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #eef0f8'>{p.get('setor','')}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #eef0f8'>{p.get('atribuicao') or '—'}</td>"
                f"<td style='padding:7px 10px;border-bottom:1px solid #eef0f8;text-align:center'>"
                f"<span style='background:{cor}22;color:{cor};padding:2px 9px;"
                f"border-radius:999px;font-weight:700;font-size:.78rem'>{dias}d</span></td>"
                f"</tr>"
            )
        rows = "".join(_critical_row(p) for p in criticos)
        criticos_section = f"""
    <div style="margin:24px 0">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#bf3535;border-radius:2px;flex-shrink:0"></div>
        <h2 style="margin:0;font-size:.95rem;font-weight:800;color:#273168;text-transform:uppercase;
                   letter-spacing:.06em">Processos mais antigos sem movimentação (top 5)</h2>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:white;border-radius:8px;border:1px solid #e8eaf0;border-collapse:collapse">
        <thead>
          <tr style="background:#f5f6fb">
            <th style="padding:7px 10px;text-align:left;font-size:.72rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Protocolo</th>
            <th style="padding:7px 10px;text-align:left;font-size:.72rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Setor</th>
            <th style="padding:7px 10px;text-align:left;font-size:.72rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Atribuição</th>
            <th style="padding:7px 10px;text-align:center;font-size:.72rem;color:#5a6390;text-transform:uppercase;letter-spacing:.06em">Dias</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

    # ── KPIs da visão geral ───────────────────────────────────────────
    mais_30 = contagens.get("mais_de_30", 0)
    mais_45 = contagens.get("mais_de_45", contagens.get("mais_de_30", 0))
    kpi_section = f"""
    <div style="margin:24px 0">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
        <div style="width:3px;height:18px;background:#f39320;border-radius:2px;flex-shrink:0"></div>
        <h2 style="margin:0;font-size:.95rem;font-weight:800;color:#273168;text-transform:uppercase;
                   letter-spacing:.06em">Visão geral — {ref}</h2>
      </div>
      <table width="100%" cellpadding="0" cellspacing="10">
        <tr>
          <td width="25%" style="background:#f5f6fb;padding:16px;border-radius:10px;
                                  border-top:3px solid #273168;text-align:center">
            <div style="font-size:1.8rem;font-weight:800;color:#273168">
              {kpis.get('total_processos_ativos', 0)}{delta_str}</div>
            <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Processos ativos</div>
          </td>
          <td width="25%" style="background:#f5f6fb;padding:16px;border-radius:10px;
                                  border-top:3px solid #5a6390;text-align:center">
            <div style="font-size:1.8rem;font-weight:800;color:#1a2050">
              {stats_bal.get('total_servidores', 0)}</div>
            <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Servidores</div>
          </td>
          <td width="25%" style="background:#fff8f0;padding:16px;border-radius:10px;
                                  border-top:3px solid #d4750e;text-align:center">
            <div style="font-size:1.8rem;font-weight:800;color:#d4750e">{mais_30}</div>
            <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Processos &gt;30 dias</div>
          </td>
          <td width="25%" style="background:#fff3f3;padding:16px;border-radius:10px;
                                  border-top:3px solid #bf3535;text-align:center">
            <div style="font-size:1.8rem;font-weight:800;color:#bf3535">{mais_45}</div>
            <div style="font-size:.7rem;color:#5a6390;text-transform:uppercase;
                        letter-spacing:.07em;margin-top:4px">Processos &gt;45 dias</div>
          </td>
        </tr>
      </table>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:20px 0;background:#dde0ea;font-family:Arial,sans-serif;color:#1a2050">

  <!-- Wrapper A4 -->
  <div style="max-width:794px;margin:0 auto;background:#ffffff;
              box-shadow:0 4px 32px rgba(39,49,104,.18);border-radius:4px;overflow:hidden">

    <!-- Cabeçalho -->
    <div style="background:linear-gradient(140deg,#273168,#1c2350,#111840);
                padding:28px 40px 24px;position:relative;overflow:hidden">
      <div style="position:absolute;top:-30px;right:-30px;width:130px;height:130px;
                  border-radius:50%;background:rgba(243,147,32,.12)"></div>
      <div style="position:absolute;bottom:-40px;left:-20px;width:100px;height:100px;
                  border-radius:50%;background:rgba(129,199,238,.07)"></div>
      <p style="margin:0 0 3px;font-size:.68rem;font-weight:700;letter-spacing:.16em;
                text-transform:uppercase;color:rgba(254,187,18,.85)">SEI BI · COPAG · PROGEP · UFC</p>
      <h1 style="margin:0 0 6px;font-size:1.5rem;font-weight:800;color:#fff;line-height:1.1">
        Relatório Semanal</h1>
      <p style="margin:0;color:rgba(240,244,255,.65);font-size:.85rem">
        Semana de {flow.get('semana_ini','')} a {flow.get('semana_fim','')}
        &nbsp;·&nbsp; Gerado em {hoje_str}
      </p>
    </div>
    <div style="height:3px;background:linear-gradient(90deg,#f39320,#febb12)"></div>

    <!-- Corpo -->
    <div style="padding:28px 40px 32px;background:#fafbff">

      {kpi_section}
      {flow_section}
      {sobrecarga_section}
      {criticos_section}
      {setor_section}

      <!-- Divisor -->
      <div style="height:1px;background:#e8eaf0;margin:28px 0 20px"></div>

      <!-- Rodapé -->
      <p style="margin:0;color:#aaa;font-size:.75rem;text-align:center;line-height:1.6">
        Gerado automaticamente pelo BI COPAG &nbsp;·&nbsp;
        <a href="https://bi-copag.vercel.app" style="color:#273168;font-weight:700">
          bi-copag.vercel.app</a><br>
        Este e-mail é confidencial e destinado exclusivamente aos gestores da COPAG/PROGEP/UFC.
      </p>
    </div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Envio do e-mail
# ---------------------------------------------------------------------------

def send_email(html: str) -> None:
    """Envia o relatório HTML via Google Workspace (smtp.gmail.com:465)."""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    recipients = os.environ["REPORT_RECIPIENTS"]

    sem_ini = date.today() - timedelta(days=date.today().weekday())
    sem_label = f"{sem_ini.strftime('%d/%m')}–{date.today().strftime('%d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 BI COPAG — Relatório semanal {sem_label}"
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

    today = date.today()
    dashboard = fetch("/api/analytics/dashboard")
    balance   = fetch("/api/analytics/workload-balance")
    stale     = fetch("/api/analytics/stale")

    print("Coletando fluxo semanal...")
    flow = fetch_weekly_flow(today)

    print(f"  Esta semana : {flow['this_entradas']} entradas, {flow['this_saidas']} saídas")
    print(f"  Semana ant. : {flow['prev_entradas']} entradas, {flow['prev_saidas']} saídas")

    print("Gerando HTML do relatório...")
    html = build_html(dashboard, balance, stale, flow)

    print("Enviando e-mail...")
    send_email(html)

    print(f"✓ Relatório semanal enviado para: {os.environ['REPORT_RECIPIENTS']}")

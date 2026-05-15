#!/usr/bin/env python3
"""
Relatório gerencial semanal — SEI Analytics
=======================================
Coleta dados da API do SEI Analytics via API key, gera um e-mail HTML com os
principais indicadores da semana e envia via Google Workspace (smtp.gmail.com).

Disparado automaticamente toda sexta-feira pelo GitHub Actions.
Pode ser disparado manualmente em qualquer momento via workflow_dispatch.

Variáveis de ambiente necessárias:
    BI_API_URL          URL da API do SEI Analytics
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
# Coleta de dados da API do SEI Analytics
# ---------------------------------------------------------------------------

DEFAULT_BI_API_URL = "https://bi-copag-api.onrender.com"
LEGACY_BI_API_URLS = {
    "https://sei-bi-copag-andersoncfs-api.onrender.com",
}


def _BASE_URL() -> str:
    url = os.getenv("BI_API_URL", DEFAULT_BI_API_URL).rstrip("/")
    if url in LEGACY_BI_API_URLS:
        print(f"  Aviso: BI_API_URL aponta para serviço antigo/suspenso ({url}).")
        print(f"  Usando API ativa: {DEFAULT_BI_API_URL}")
        return DEFAULT_BI_API_URL
    return url


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
    """Chama um endpoint analítico do SEI Analytics usando API key, com retry automático."""
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
    Retorna totais de entradas e saídas para a semana do relatório e a semana anterior.

    Estratégia: carrega uma única janela de 3 semanas (21 dias antes de this_mon),
    garantindo que sempre exista pelo menos um snapshot como baseline ANTES das
    duas semanas de interesse — mesmo que a sexta imediatamente anterior seja feriado
    (ex: 01/05 = Dia do Trabalho) e não tenha snapshot.

    O primeiro snapshot carregado vira o baseline inflado (entradas = carga total),
    mas como está fora dos conjuntos this_week e prev_week, é corretamente excluído
    da soma. Cada dia das semanas de interesse é então comparado contra o snapshot
    real do dia anterior na sequência disponível.
    """
    this_mon     = report_date - timedelta(days=report_date.weekday())
    prev_mon     = this_mon - timedelta(weeks=1)
    last_friday  = this_mon - timedelta(days=3)
    far_baseline = this_mon - timedelta(days=21)   # 3 semanas: garante baseline real

    flow_data = fetch(
        "/api/analytics/entries-exits",
        data_inicial=far_baseline.isoformat(),
        data_final=report_date.isoformat(),
    )

    series    = flow_data.get("evolucao_fluxo", [])
    this_week = {str(this_mon + timedelta(days=i)) for i in range(5)}
    prev_week = {str(prev_mon  + timedelta(days=i)) for i in range(5)}

    def _sum_flow(series: list, dates: set) -> tuple[int, int]:
        ent = sum(item["entradas"] for item in series if item["date"] in dates)
        sai = sum(item["saidas"]   for item in series if item["date"] in dates)
        return ent, sai

    this_e, this_s = _sum_flow(series, this_week)
    prev_e, prev_s = _sum_flow(series, prev_week)

    return {
        "this_entradas": this_e,
        "this_saidas":   this_s,
        "prev_entradas": prev_e,
        "prev_saidas":   prev_s,
        "semana_ini":     this_mon.strftime("%d/%m"),
        "semana_fim":     report_date.strftime("%d/%m"),
        "semana_ant_ini": prev_mon.strftime("%d/%m"),
        "semana_ant_fim": last_friday.strftime("%d/%m"),
    }


# ---------------------------------------------------------------------------
# Geração do HTML do relatório — formato A4 premium
# ---------------------------------------------------------------------------

_FONT = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"

# Paleta semântica de severidade
_SEV: dict[str, dict] = {
    "ok":       {"bg": "#f0faf5", "border": "#1a7a50", "text": "#1a7a50",  "badge_bg": "#d1f0e3"},
    "warning":  {"bg": "#fffbeb", "border": "#9a6c00", "text": "#7a5200",  "badge_bg": "#fef3c7"},
    "alert":    {"bg": "#fff8f0", "border": "#d4750e", "text": "#b85e08",  "badge_bg": "#ffedd5"},
    "serious":  {"bg": "#fff5f5", "border": "#c0392b", "text": "#9b1c1c",  "badge_bg": "#fce8e8"},
    "critical": {"bg": "#fef0f0", "border": "#b71c1c", "text": "#7f1d1d",  "badge_bg": "#fcd5d5"},
    "extreme":  {"bg": "#f5f0ff", "border": "#4a148c", "text": "#3b0764",  "badge_bg": "#ede9fe"},
}


def _sev_key(dias: int) -> str:
    if dias >= 90: return "extreme"
    if dias >= 60: return "critical"
    if dias >= 45: return "serious"
    if dias >= 30: return "alert"
    if dias >= 15: return "warning"
    return "ok"


def _delta_tag(atual: int, anterior: int, lower_is_better: bool = False) -> str:
    """Badge inline de variação vs semana anterior."""
    if anterior == 0 or atual == anterior:
        return ""
    diff = atual - anterior
    positivo = diff > 0
    if lower_is_better:
        cor = "#bf3535" if positivo else "#1a7a50"
    else:
        cor = "#1a7a50" if positivo else "#bf3535"
    seta = "▲" if positivo else "▼"
    return (
        f"<span style='display:inline-block;margin-left:6px;padding:2px 8px;"
        f"border-radius:999px;font-size:.7rem;font-weight:700;"
        f"background:{cor}18;color:{cor}'>{seta}{abs(diff)}</span>"
    )


def _section_title(label: str, color: str = "#f39320") -> str:
    return (
        f"<table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:14px'>"
        f"<tr>"
        f"<td width='3' style='background:{color};border-radius:2px'>&nbsp;</td>"
        f"<td style='padding:0 0 0 10px'>"
        f"<span style='font-family:{_FONT};font-size:.78rem;font-weight:800;"
        f"color:#273168;text-transform:uppercase;letter-spacing:.1em'>{label}</span>"
        f"</td></tr></table>"
    )


def build_html(dashboard: dict, balance: dict, stale: dict, flow: dict) -> str:
    kpis       = dashboard.get("kpis", {})
    setores    = sorted(dashboard.get("por_setor", []), key=lambda x: -x["value"])
    servidores = balance.get("servidores", [])
    stats_bal  = balance.get("stats", {})
    contagens  = stale.get("contagens", {})
    criticos   = stale.get("processos", [])[:5]
    sobrecarga = [s for s in servidores if s.get("status") == "sobrecarga"]

    hoje_str = date.today().strftime("%d/%m/%Y")
    ref       = dashboard.get("data_referencia", "")
    sem_ini   = flow.get("semana_ini", "")
    sem_fim   = flow.get("semana_fim", "")

    this_e = flow.get("this_entradas", 0)
    this_s = flow.get("this_saidas",   0)
    prev_e = flow.get("prev_entradas", 0)
    prev_s = flow.get("prev_saidas",   0)
    # Saldo = soma das variações diárias por setor durante a semana (entradas - saídas).
    # Inclui transferências entre setores (cada transferência gera 1 entrada + 1 saída,
    # que se cancelam no saldo). Representa o fluxo líquido real da semana.
    saldo = this_e - this_s
    mais_30 = contagens.get("mais_de_30", 0)
    mais_45 = contagens.get("mais_de_45", contagens.get("mais_de_30", 0))
    total_ativos = kpis.get("total_processos_ativos", 0)
    total_serv   = stats_bal.get("total_servidores", 0)

    # ── KPIs — saldo semanal exibido abaixo de "Processos ativos" ────
    delta_ativos = ""
    if saldo != 0:
        cor  = "#bf3535" if saldo > 0 else "#1a7a50"
        seta = "▲" if saldo > 0 else "▼"
        delta_ativos = (
            f"<div style='margin-top:6px;display:inline-block;padding:2px 9px;"
            f"border-radius:999px;background:{cor}18;color:{cor};"
            f"font-size:.72rem;font-weight:700'>Saldo semanal: {seta}{abs(saldo)}</div>"
        )

    def _kpi_card(value: str, label: str, accent: str, bg: str, extra: str = "") -> str:
        return (
            f"<td style='padding:5px'>"
            f"<table width='100%' cellpadding='0' cellspacing='0' style='"
            f"background:{bg};border-radius:12px;border:1px solid {accent}30;"
            f"border-top:3px solid {accent}'>"
            f"<tr><td style='padding:18px 16px;text-align:center'>"
            f"<div style='font-family:{_FONT};font-size:2rem;font-weight:800;color:{accent};"
            f"line-height:1'>{value}</div>"
            f"{extra}"
            f"<div style='font-family:{_FONT};font-size:.68rem;font-weight:700;"
            f"color:#5a6390;text-transform:uppercase;letter-spacing:.09em;margin-top:8px'>"
            f"{label}</div>"
            f"</td></tr></table></td>"
        )

    kpi_section = (
        f"<div style='margin:0 0 28px'>"
        + _section_title(f"Visão geral &nbsp;·&nbsp; {ref}")
        + f"<table width='100%' cellpadding='0' cellspacing='0'><tr>"
        + _kpi_card(str(total_ativos), "Processos ativos",    "#273168", "#f4f5fc", delta_ativos)
        + _kpi_card(str(total_serv),   "Servidores",          "#5a6390", "#f5f6fb")
        + _kpi_card(str(mais_30),      "Acima de 30 dias",   "#d4750e", "#fff8f0")
        + _kpi_card(str(mais_45),      "Acima de 45 dias",   "#bf3535", "#fff3f3")
        + f"</tr></table></div>"
    )

    # ── Fluxo da semana ──────────────────────────────────────────────
    saldo_cor   = "#d4750e" if saldo > 0 else "#1a7a50" if saldo < 0 else "#5a6390"
    saldo_bg    = "#fff8f0" if saldo > 0 else "#f0faf5" if saldo < 0 else "#f5f6fb"
    saldo_label = "Acúmulo" if saldo > 0 else "Redução" if saldo < 0 else "Equilíbrio"
    saldo_str   = f"+{saldo}" if saldo > 0 else str(saldo)

    flow_section = (
        f"<div style='margin:0 0 28px'>"
        + _section_title(f"Fluxo da semana &nbsp;·&nbsp; {sem_ini} – {sem_fim}")
        + f"""<table width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <!-- Entraram -->
    <td width="33%" style="padding:0 5px 0 0">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f0faf5;border-radius:12px;border:1px solid #1a7a5030;
                    border-left:4px solid #1a7a50">
        <tr><td style="padding:18px 16px">
          <div style="font-family:{_FONT};font-size:.68rem;font-weight:700;color:#1a7a50;
                      text-transform:uppercase;letter-spacing:.1em">Entraram</div>
          <div style="font-family:{_FONT};font-size:2.2rem;font-weight:800;color:#1a7a50;
                      line-height:1;margin:8px 0 4px">
            {this_e}{_delta_tag(this_e, prev_e)}</div>
          <div style="font-family:{_FONT};font-size:.75rem;color:#5a6390">
            Sem. ant.: <strong>{prev_e}</strong></div>
        </td></tr>
      </table>
    </td>
    <!-- Saldo -->
    <td width="34%" style="padding:0 5px">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:{saldo_bg};border-radius:12px;border:1px solid {saldo_cor}30;
                    border-left:4px solid {saldo_cor}">
        <tr><td style="padding:18px 16px">
          <div style="font-family:{_FONT};font-size:.68rem;font-weight:700;color:{saldo_cor};
                      text-transform:uppercase;letter-spacing:.1em">Saldo líquido</div>
          <div style="font-family:{_FONT};font-size:2.2rem;font-weight:800;color:{saldo_cor};
                      line-height:1;margin:8px 0 4px">{saldo_str}</div>
          <div style="font-family:{_FONT};font-size:.75rem;color:#5a6390">{saldo_label} de carga</div>
        </td></tr>
      </table>
    </td>
    <!-- Saíram -->
    <td width="33%" style="padding:0 0 0 5px">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#fff8f0;border-radius:12px;border:1px solid #f3932030;
                    border-left:4px solid #f39320">
        <tr><td style="padding:18px 16px">
          <div style="font-family:{_FONT};font-size:.68rem;font-weight:700;color:#d4750e;
                      text-transform:uppercase;letter-spacing:.1em">Saíram</div>
          <div style="font-family:{_FONT};font-size:2.2rem;font-weight:800;color:#d4750e;
                      line-height:1;margin:8px 0 4px">
            {this_s}{_delta_tag(this_s, prev_s, lower_is_better=True)}</div>
          <div style="font-family:{_FONT};font-size:.75rem;color:#5a6390">
            Sem. ant.: <strong>{prev_s}</strong></div>
        </td></tr>
      </table>
    </td>
  </tr>
</table>
</div>"""
    )

    # ── Sobrecarga ────────────────────────────────────────────────────
    sobrecarga_section = ""
    if sobrecarga:
        def _sob_delta(s: dict) -> str:
            if s.get("delta") and s["delta"] > 0:
                return (f"<span style='margin-left:6px;padding:1px 7px;border-radius:999px;"
                        f"background:#bf353518;color:#bf3535;font-size:.7rem;font-weight:700'>"
                        f"▲{abs(s['delta'])}</span>")
            return ""
        rows_sob = "".join(
            f"<tr style='{'background:#fff5f5' if i%2==0 else 'background:#fff'}'>"
            f"<td style='padding:9px 12px;font-family:{_FONT};font-weight:600;font-size:.85rem;"
            f"color:#1a2050'>{s['atribuicao']}</td>"
            f"<td style='padding:9px 12px;text-align:center;font-family:{_FONT};"
            f"font-weight:800;color:#bf3535;font-size:.95rem'>{s['carga']}</td>"
            f"<td style='padding:9px 12px;text-align:center;font-family:{_FONT};"
            f"color:#5a6390;font-size:.82rem'>{s['pct_total']}%{_sob_delta(s)}</td>"
            f"</tr>"
            for i, s in enumerate(sobrecarga)
        )
        sobrecarga_section = f"""
<div style="margin:0 0 28px">
  {_section_title(f"&#9888; Servidores em sobrecarga &nbsp;({len(sobrecarga)})", "#bf3535")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-radius:10px;border:1.5px solid #bf353530;border-collapse:collapse;overflow:hidden">
    <thead>
      <tr style="background:#fff0f0">
        <th style="padding:8px 12px;text-align:left;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Servidor</th>
        <th style="padding:8px 12px;text-align:center;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em;font-weight:700">Processos</th>
        <th style="padding:8px 12px;text-align:center;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em;font-weight:700">% do total</th>
      </tr>
    </thead>
    <tbody>{rows_sob}</tbody>
  </table>
</div>"""

    # ── Processos críticos ────────────────────────────────────────────
    criticos_section = ""
    if criticos:
        def _critical_row(p: dict, i: int) -> str:
            dias  = p.get("dias_sem_movimentacao", 0)
            sev   = _SEV[_sev_key(dias)]
            bg_row = "#fafbff" if i % 2 == 0 else "#ffffff"
            return (
                f"<tr style='background:{bg_row}'>"
                f"<td style='padding:9px 12px;font-family:\"Courier New\",Courier,monospace;"
                f"font-size:.8rem;color:#273168;font-weight:600'>{p.get('protocolo','')}</td>"
                f"<td style='padding:9px 12px;font-family:{_FONT};font-size:.82rem;color:#5a6390'>"
                f"{p.get('setor','')}</td>"
                f"<td style='padding:9px 12px;font-family:{_FONT};font-size:.82rem;color:#1a2050'>"
                f"{p.get('atribuicao') or '—'}</td>"
                f"<td style='padding:9px 12px;text-align:center'>"
                f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;"
                f"background:{sev['badge_bg']};color:{sev['text']};"
                f"font-family:{_FONT};font-size:.75rem;font-weight:800;"
                f"border:1px solid {sev['border']}40'>{dias}d</span></td>"
                f"</tr>"
            )
        rows_crit = "".join(_critical_row(p, i) for i, p in enumerate(criticos))
        criticos_section = f"""
<div style="margin:0 0 28px">
  {_section_title("Processos mais antigos sem movimentação &nbsp;· top 5", "#c0392b")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-radius:10px;border:1px solid #e8eaf0;border-collapse:collapse;overflow:hidden">
    <thead>
      <tr style="background:#f5f6fb;border-bottom:1.5px solid #e0e4f0">
        <th style="padding:8px 12px;text-align:left;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Protocolo</th>
        <th style="padding:8px 12px;text-align:left;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Setor</th>
        <th style="padding:8px 12px;text-align:left;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Atribuição</th>
        <th style="padding:8px 12px;text-align:center;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Tempo</th>
      </tr>
    </thead>
    <tbody>{rows_crit}</tbody>
  </table>
</div>"""

    # ── Distribuição por setor com barras visuais ─────────────────────
    setor_section = ""
    if setores:
        total_s = sum(s["value"] for s in setores) or 1
        def _setor_bar(s: dict, i: int) -> str:
            pct   = round(s["value"] / total_s * 100)
            bar_w = max(2, pct)  # mínimo visível
            bg    = "#f5f6fb" if i % 2 == 0 else "#ffffff"
            return (
                f"<tr style='background:{bg}'>"
                f"<td width='120' style='padding:9px 12px;font-family:{_FONT};"
                f"font-weight:700;font-size:.85rem;color:#273168'>{s['label']}</td>"
                f"<td style='padding:9px 8px 9px 4px'>"
                f"<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                f"<td width='{bar_w}%' style='background:linear-gradient(90deg,#273168,#3d4fa0);"
                f"height:10px;border-radius:999px'></td>"
                f"<td width='{100 - bar_w}%'></td>"
                f"</tr></table>"
                f"</td>"
                f"<td width='56' style='padding:9px 12px;text-align:right;font-family:{_FONT};"
                f"font-weight:800;font-size:.95rem;color:#273168'>{s['value']}</td>"
                f"<td width='42' style='padding:9px 8px 9px 0;font-family:{_FONT};"
                f"font-size:.72rem;color:#9a9fc0'>{pct}%</td>"
                f"</tr>"
            )
        setor_rows = "".join(_setor_bar(s, i) for i, s in enumerate(setores))
        setor_section = f"""
<div style="margin:0 0 28px">
  {_section_title("Distribuição por setor")}
  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-radius:10px;border:1px solid #e8eaf0;border-collapse:collapse;overflow:hidden">
    <thead>
      <tr style="background:#f5f6fb;border-bottom:1.5px solid #e0e4f0">
        <th style="padding:8px 12px;text-align:left;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Setor</th>
        <th style="padding:8px 12px;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em"></th>
        <th width="56" style="padding:8px 12px;text-align:right;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">Proc.</th>
        <th width="42" style="padding:8px 8px;font-family:{_FONT};font-size:.7rem;
                   color:#5a6390;text-transform:uppercase;letter-spacing:.08em">%</th>
      </tr>
    </thead>
    <tbody>{setor_rows}</tbody>
  </table>
</div>"""

    # ── Monta o documento ─────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:24px 0 32px;background:#dde0ea;font-family:{_FONT};color:#1a2050">

  <div style="max-width:794px;margin:0 auto;border-radius:6px;overflow:hidden;
              box-shadow:0 8px 40px rgba(39,49,104,.2)">

    <!-- Tarja superior laranja -->
    <div style="height:4px;background:linear-gradient(90deg,#f39320,#febb12,#f39320)"></div>

    <!-- Cabeçalho -->
    <div style="background:linear-gradient(135deg,#273168 0%,#1c2350 55%,#111840 100%);
                padding:32px 44px 28px">
      <!-- Linha de identificação -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px">
        <tr>
          <td>
            <span style="font-family:{_FONT};font-size:.65rem;font-weight:800;
                         letter-spacing:.2em;text-transform:uppercase;
                         color:rgba(254,187,18,.85)">SEI Analytics &nbsp;·&nbsp; COPAG &nbsp;·&nbsp;
                         PROGEP &nbsp;·&nbsp; UFC</span>
          </td>
          <td style="text-align:right">
            <span style="font-family:{_FONT};font-size:.75rem;color:rgba(240,244,255,.45)">
              {hoje_str}</span>
          </td>
        </tr>
      </table>
      <!-- Título + período -->
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <div style="font-family:{_FONT};font-size:1.75rem;font-weight:800;
                        color:#ffffff;line-height:1.05;margin-bottom:6px">
              Relatório Semanal</div>
            <div style="font-family:{_FONT};font-size:.88rem;color:rgba(240,244,255,.62)">
              Semana de <strong style="color:rgba(254,187,18,.9)">{sem_ini}</strong>
              a <strong style="color:rgba(254,187,18,.9)">{sem_fim}</strong>
              &nbsp;·&nbsp; Referência: {ref}
            </div>
          </td>
          <td style="text-align:right;vertical-align:top">
            <!-- Chip resumo rápido -->
            <div style="display:inline-block;background:rgba(243,147,32,.18);
                        border:1px solid rgba(243,147,32,.3);border-radius:8px;
                        padding:10px 16px;text-align:center">
              <div style="font-family:{_FONT};font-size:1.5rem;font-weight:800;
                           color:#febb12;line-height:1">{total_ativos}</div>
              <div style="font-family:{_FONT};font-size:.65rem;font-weight:700;
                           color:rgba(240,244,255,.55);text-transform:uppercase;
                           letter-spacing:.1em;margin-top:3px">processos</div>
            </div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Corpo -->
    <div style="background:#f8f9fd;padding:32px 44px 36px">

      {kpi_section}

      <!-- Separador -->
      <div style="height:1px;background:linear-gradient(90deg,transparent,#d0d4e8,transparent);
                  margin:0 0 28px"></div>

      {flow_section}

      <!-- Separador -->
      <div style="height:1px;background:linear-gradient(90deg,transparent,#d0d4e8,transparent);
                  margin:0 0 28px"></div>

      {sobrecarga_section}
      {criticos_section}
      {setor_section}

      <!-- Rodapé -->
      <div style="height:1px;background:#e0e4f0;margin:4px 0 24px"></div>
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:{_FONT};font-size:.72rem;color:#9a9fc0;line-height:1.7">
            Gerado automaticamente pelo
            <a href="https://bi-copag.vercel.app"
               style="color:#273168;font-weight:700;text-decoration:none">SEI Analytics</a>
            &nbsp;·&nbsp; Toda sexta-feira às 20h BRT<br>
            Confidencial — exclusivo para gestores da COPAG/PROGEP/UFC.
          </td>
          <td style="text-align:right;vertical-align:top">
            <span style="font-family:{_FONT};font-size:.65rem;color:#c0c4d8;
                         text-transform:uppercase;letter-spacing:.08em">bi-copag.vercel.app</span>
          </td>
        </tr>
      </table>

    </div>

    <!-- Tarja inferior -->
    <div style="height:4px;background:linear-gradient(90deg,#273168,#3d4fa0,#273168)"></div>

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
    msg["Subject"] = f"📊 SEI Analytics — Relatório semanal {sem_label}"
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
    print("Coletando dados do SEI Analytics...")
    _warmup()

    today = date.today()
    dashboard = fetch("/api/analytics/dashboard")
    balance   = fetch("/api/analytics/workload-balance")
    stale     = fetch("/api/analytics/stale")

    print("Coletando fluxo semanal...")
    flow = fetch_weekly_flow(today)

    saldo_semana = flow["this_entradas"] - flow["this_saidas"]
    print(f"  Esta semana : {flow['this_entradas']} entradas, {flow['this_saidas']} saídas"
          f" (saldo: {saldo_semana:+d})")
    print(f"  Semana ant. : {flow['prev_entradas']} entradas, {flow['prev_saidas']} saídas")

    print("Gerando HTML do relatório...")
    html = build_html(dashboard, balance, stale, flow)

    print("Enviando e-mail...")
    send_email(html)

    print(f"✓ Relatório semanal enviado para: {os.environ['REPORT_RECIPIENTS']}")

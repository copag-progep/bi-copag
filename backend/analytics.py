from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from threading import Lock

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Processo, Upload


@dataclass(frozen=True)
class AnalyticsFilters:
    data_referencia: date | None = None
    data_inicial: date | None = None
    data_final: date | None = None
    setor: str | None = None
    tipo: str | None = None
    atribuicao: str | None = None

    def cache_key(self) -> tuple[object, ...]:
        return (
            self.data_referencia,
            self.data_inicial,
            self.data_final,
            self.setor,
            self.tipo,
            self.atribuicao,
        )


PROCESS_FIELDS = [
    "protocolo",
    "atribuicao",
    "tipo",
    "especificacao",
    "ponto_controle",
    "data_autuacao",
    "data_recebimento",
    "data_envio",
    "unidade_envio",
    "observacoes",
    "setor",
    "data_relatorio",
]

PROCESS_COLUMN_MAP = {
    "protocolo": Processo.protocolo,
    "atribuicao": Processo.atribuicao_normalizada,
    "tipo": Processo.tipo,
    "especificacao": Processo.especificacao,
    "ponto_controle": Processo.ponto_controle,
    "data_autuacao": Processo.data_autuacao,
    "data_recebimento": Processo.data_recebimento,
    "data_envio": Processo.data_envio,
    "unidade_envio": Processo.unidade_envio,
    "observacoes": Processo.observacoes,
    "setor": Processo.setor,
    "data_relatorio": Processo.data_relatorio,
}

PROCESS_FIELD_DEFAULTS = {
    "atribuicao": "Não informado",
    "tipo": "Não informado",
    "especificacao": "",
    "ponto_controle": "Não informado",
    "unidade_envio": "Não informado",
    "observacoes": "",
}

FLOW_FIELDS = ["protocolo", "setor", "data_relatorio"]
SPAN_FIELDS = ["protocolo", "atribuicao", "tipo", "setor", "data_relatorio"]
ASSIGNMENT_FIELDS = ["protocolo", "atribuicao", "setor", "data_relatorio"]
ATTRIBUTION_FIELDS = ["protocolo", "atribuicao", "tipo", "setor", "data_relatorio"]

_ANALYTICS_CACHE: dict[tuple[object, ...], dict] = {}
_CACHE_LOCK = Lock()

_SIG_CACHE: tuple[tuple, float] | None = None
_SIG_TTL = 5.0  # segundos — evita roundtrip ao banco em requests consecutivos

# Janela máxima de histórico quando nenhum filtro de data é definido.
# Limita quanto dado é lido do banco em cold starts e no precompute de startup.
# Ajuste via env var ANALYTICS_LOOKBACK_DAYS (0 = sem limite).
_ANALYTICS_LOOKBACK_DAYS = int(os.getenv("ANALYTICS_LOOKBACK_DAYS", "120"))

# ── Score de Risco — pesos e thresholds configuráveis via env vars ─────────
# Fórmula: score = min((W_ABS×D_abs + W_REL×D_rel + W_UNASSIGNED×A + W_MULTI×V) × T, 1.0)
# D_abs = min(dias/90, 1.0)  ·  D_rel = min(dias/p90, 2.0)/2.0
# A, V ∈ {0, 1}  ·  T ∈ {TREND_DOWN, TREND_STABLE, TREND_UP}
_RISK_W_ABS        = float(os.getenv("RISK_WEIGHT_ABS",        "0.40"))
_RISK_W_REL        = float(os.getenv("RISK_WEIGHT_REL",        "0.35"))
_RISK_W_UNASSIGNED = float(os.getenv("RISK_WEIGHT_UNASSIGNED", "0.15"))
_RISK_W_MULTI      = float(os.getenv("RISK_WEIGHT_MULTI_SECTOR","0.10"))
_RISK_TREND_UP     = float(os.getenv("RISK_TREND_UP",           "1.20"))
_RISK_TREND_STABLE = float(os.getenv("RISK_TREND_STABLE",       "1.00"))
_RISK_TREND_DOWN   = float(os.getenv("RISK_TREND_DOWN",         "0.85"))
_RISK_THR_CRITICAL = float(os.getenv("RISK_CRITICAL_THRESHOLD", "0.70"))
_RISK_THR_HIGH     = float(os.getenv("RISK_HIGH_THRESHOLD",     "0.45"))
_RISK_THR_MODERATE = float(os.getenv("RISK_MODERATE_THRESHOLD", "0.20"))
_RISK_MIN_SAMPLE   = int(os.getenv("RISK_MIN_LT_SAMPLE",        "5"))
_RISK_MIN_P90_DAYS = float(os.getenv("RISK_MIN_P90_DAYS",       "7"))
_RISK_ABS_NORM     = 90  # dias considerados como 100% no fator de tempo absoluto


def clear_analytics_cache() -> None:
    global _SIG_CACHE
    with _CACHE_LOCK:
        _ANALYTICS_CACHE.clear()
        _SIG_CACHE = None


def _uploads_signature(db: Session) -> tuple[object, ...]:
    """Retorna uma tupla (total, max_id, max_timestamp) usada como chave de invalidação do cache."""
    global _SIG_CACHE
    now = time.monotonic()
    if _SIG_CACHE is not None and now - _SIG_CACHE[1] < _SIG_TTL:
        return _SIG_CACHE[0]

    total_uploads, latest_upload_id, latest_upload_time = (
        db.query(
            func.count(Upload.id),
            func.max(Upload.id),
            func.max(Upload.data_upload),
        ).one()
    )
    sig = (
        int(total_uploads or 0),
        int(latest_upload_id or 0),
        latest_upload_time.isoformat() if isinstance(latest_upload_time, datetime) else None,
    )
    _SIG_CACHE = (sig, now)
    return sig


def _cached_response(
    db: Session,
    cache_name: str,
    filters: AnalyticsFilters | None,
    builder: Callable[[], dict],
) -> dict:
    """Retorna resposta do cache ou executa builder e armazena. Invalida automaticamente quando uploads mudam."""
    key = (
        cache_name,
        _uploads_signature(db),
        filters.cache_key() if filters else None,
    )
    with _CACHE_LOCK:
        cached = _ANALYTICS_CACHE.get(key)
    if cached is not None:
        return cached

    payload = builder()
    with _CACHE_LOCK:
        _ANALYTICS_CACHE[key] = payload
    return payload


def _base_query(db: Session, filters: AnalyticsFilters):
    query = db.query(Processo)
    if filters.setor:
        query = query.filter(Processo.setor == filters.setor.upper())
    if filters.tipo:
        query = query.filter(Processo.tipo == filters.tipo)
    if filters.atribuicao:
        if filters.atribuicao == "__sem_atribuicao__":
            query = query.filter(Processo.atribuicao_normalizada.is_(None))
        else:
            query = query.filter(Processo.atribuicao_normalizada == filters.atribuicao)
    if filters.data_inicial:
        query = query.filter(Processo.data_relatorio >= filters.data_inicial)
    if filters.data_final:
        query = query.filter(Processo.data_relatorio <= filters.data_final)
    return query


def _normalize_fields(fields: Sequence[str] | None) -> list[str]:
    requested = list(dict.fromkeys(fields or PROCESS_FIELDS))
    if "data_relatorio" not in requested:
        requested.append("data_relatorio")
    return requested


def _rows_to_dataframe(rows: list[tuple], fields: Sequence[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=list(fields) + ["report_day"])

    frame = pd.DataFrame.from_records(rows, columns=list(fields))
    for field, default_value in PROCESS_FIELD_DEFAULTS.items():
        if field in frame.columns:
            frame[field] = frame[field].fillna(default_value)

    if "data_relatorio" in frame.columns:
        frame["data_relatorio"] = pd.to_datetime(frame["data_relatorio"])
        frame["report_day"] = frame["data_relatorio"].dt.date

    return frame


def _distinct_values(db: Session, column) -> list:
    values = (
        db.query(column)
        .filter(column.is_not(None))
        .distinct()
        .order_by(column.asc())
        .all()
    )
    return [row[0] for row in values if row[0] not in (None, "")]


def get_filter_options(db: Session) -> dict:
    def build() -> dict:
        datas = [
            row[0]
            for row in db.query(Processo.data_relatorio)
            .distinct()
            .order_by(Processo.data_relatorio.asc())
            .all()
            if row[0]
        ]
        return {
            "datas": datas,
            "setores": _distinct_values(db, Processo.setor),
            "tipos": _distinct_values(db, Processo.tipo),
            "atribuicoes": _distinct_values(db, Processo.atribuicao_normalizada),
        }

    return _cached_response(db, "filter-options", None, build)


def _available_dates(db: Session, filters: AnalyticsFilters | None = None) -> list[date]:
    query = db.query(Processo)
    if filters:
        if filters.setor:
            query = query.filter(Processo.setor == filters.setor.upper())
        if filters.tipo:
            query = query.filter(Processo.tipo == filters.tipo)
        if filters.atribuicao:
            if filters.atribuicao == "__sem_atribuicao__":
                query = query.filter(Processo.atribuicao_normalizada.is_(None))
            else:
                query = query.filter(Processo.atribuicao_normalizada == filters.atribuicao)
        if filters.data_inicial:
            query = query.filter(Processo.data_relatorio >= filters.data_inicial)
        if filters.data_final:
            query = query.filter(Processo.data_relatorio <= filters.data_final)

    values = (
        query.with_entities(Processo.data_relatorio)
        .distinct()
        .order_by(Processo.data_relatorio.asc())
        .all()
    )
    return [row[0] for row in values if row[0]]


def _resolve_reference_date(db: Session, filters: AnalyticsFilters) -> date | None:
    """Determina a data de referência: a solicitada (ou a mais recente disponível) dentro dos filtros."""
    dates = _available_dates(db, filters)
    if not dates:
        return None
    if not filters.data_referencia:
        return dates[-1]
    eligible = [day for day in dates if day <= filters.data_referencia]
    return eligible[-1] if eligible else dates[-1]


def _effective_filters(filters: AnalyticsFilters) -> AnalyticsFilters:
    """Aplica janela de lookback padrão quando nenhum filtro de data é definido.

    Evita carregar TODO o histórico do banco em consultas sem filtros (cold starts,
    precompute de startup, dashboard sem filtros). Se data_inicial já está definida
    pelo usuário, retorna os filtros originais sem modificação.
    """
    if filters.data_inicial is not None or _ANALYTICS_LOOKBACK_DAYS <= 0:
        return filters
    cutoff = date.today() - timedelta(days=_ANALYTICS_LOOKBACK_DAYS)
    return AnalyticsFilters(
        data_referencia=filters.data_referencia,
        data_inicial=cutoff,
        data_final=filters.data_final,
        setor=filters.setor,
        tipo=filters.tipo,
        atribuicao=filters.atribuicao,
    )


def _load_dataframe(
    db: Session,
    filters: AnalyticsFilters,
    fields: Sequence[str] | None = None,
    upto_reference: bool = True,
    apply_lookback: bool = True,
) -> tuple[pd.DataFrame, date | None, list[date]]:
    """Carrega processos do banco como DataFrame, resolve data de referência e lista de datas disponíveis."""
    # apply_lookback=False preserva histórico completo para analytics que calculam
    # duração de processos (stale, atribuições, perfil de servidor).
    effective = _effective_filters(filters) if apply_lookback else filters
    reference_date = _resolve_reference_date(db, effective)
    requested_fields = _normalize_fields(fields)

    query = _base_query(db, effective)
    if upto_reference and reference_date:
        query = query.filter(Processo.data_relatorio <= reference_date)

    columns = [PROCESS_COLUMN_MAP[field].label(field) for field in requested_fields]
    rows = [
        tuple(row)
        for row in query.with_entities(*columns).order_by(Processo.data_relatorio.asc()).all()
    ]
    frame = _rows_to_dataframe(rows, requested_fields)
    dates = sorted(frame["report_day"].unique().tolist()) if not frame.empty else []
    return frame, reference_date, dates


def _snapshot(frame: pd.DataFrame, report_date: date | None) -> pd.DataFrame:
    if frame.empty or not report_date:
        return frame.iloc[0:0]
    return frame[frame["report_day"] == report_date].copy()


def _count_series(frame: pd.DataFrame, column: str) -> list[dict]:
    if frame.empty:
        return []
    grouped = frame.groupby(column)["protocolo"].count().sort_values(ascending=False)
    return [{"label": key, "value": int(value)} for key, value in grouped.items()]


def _protocols_by_date_and_sector(frame: pd.DataFrame) -> dict[tuple[date, str], set[str]]:
    if frame.empty:
        return {}
    grouped = frame.groupby(["report_day", "setor"])["protocolo"].agg(lambda values: set(values))
    return {(day, setor): protocolos for (day, setor), protocolos in grouped.items()}


def _assignments_by_date_and_atribuicao(frame: pd.DataFrame) -> dict[tuple[date, str], set[str]]:
    if frame.empty:
        return {}

    keyed = frame[["report_day", "atribuicao", "protocolo", "setor"]].copy()
    keyed["assignment_key"] = keyed["protocolo"].astype(str) + "|" + keyed["setor"].astype(str)
    grouped = keyed.groupby(["report_day", "atribuicao"])["assignment_key"].agg(set)
    return {(day, atribuicao): assignment_keys for (day, atribuicao), assignment_keys in grouped.items()}


def _span_record(start: dict, end: dict, available_dates: list[date], idx_map: dict[date, int]) -> dict:
    """Monta um registro de permanência (span) a partir de dois pontos extremos de presença consecutiva."""
    start_day = start.get("report_day") or pd.Timestamp(start["data_relatorio"]).date()
    end_day = end.get("report_day") or pd.Timestamp(end["data_relatorio"]).date()
    end_idx = idx_map[end_day]
    next_date = available_dates[end_idx + 1] if end_idx < len(available_dates) - 1 else None
    duration_end = next_date or end_day

    return {
        "protocolo": start["protocolo"],
        "setor": start["setor"],
        "atribuicao": end.get("atribuicao", "Não informado"),
        "tipo": end.get("tipo", "Não informado"),
        "especificacao": end.get("especificacao", ""),
        "ponto_controle": end.get("ponto_controle", "Não informado"),
        "entrada_setor": start_day,
        "ultima_presenca": end_day,
        "saida_setor": next_date,
        "duracao_dias": max((duration_end - start_day).days, 0),
        "aberto": next_date is None,
    }


def _build_presence_spans(frame: pd.DataFrame, available_dates: list[date]) -> pd.DataFrame:
    """Detecta intervalos contínuos de presença de cada processo em cada setor.

    Um gap de 1+ dia no índice de datas disponíveis encerra o span atual e inicia outro.
    Spans abertos (última presença = último snapshot) indicam processos ainda ativos no setor.
    """
    if frame.empty or not available_dates:
        return pd.DataFrame(
            columns=[
                "protocolo",
                "setor",
                "atribuicao",
                "tipo",
                "especificacao",
                "ponto_controle",
                "entrada_setor",
                "ultima_presenca",
                "saida_setor",
                "duracao_dias",
                "aberto",
            ]
        )

    idx_map = {day: idx for idx, day in enumerate(available_dates)}
    ordered = frame.sort_values(["protocolo", "setor", "data_relatorio"])
    spans: list[dict] = []

    for _, group in ordered.groupby(["protocolo", "setor"], sort=False):
        records = group.to_dict(orient="records")
        start = records[0]
        previous = records[0]
        previous_idx = idx_map[previous.get("report_day") or pd.Timestamp(previous["data_relatorio"]).date()]

        for current in records[1:]:
            current_day = current.get("report_day") or pd.Timestamp(current["data_relatorio"]).date()
            current_idx = idx_map[current_day]
            if current_idx == previous_idx + 1:
                previous = current
                previous_idx = current_idx
                continue

            spans.append(_span_record(start, previous, available_dates, idx_map))
            start = current
            previous = current
            previous_idx = current_idx

        spans.append(_span_record(start, previous, available_dates, idx_map))

    return pd.DataFrame(spans)


def _previous_date(available_dates: list[date], reference_date: date | None) -> date | None:
    if not available_dates or not reference_date:
        return None
    previous = [day for day in available_dates if day < reference_date]
    return previous[-1] if previous else None


def _finalized_by_attribution(frame: pd.DataFrame, available_dates: list[date]) -> list[dict]:
    """Conta saídas por atribuição comparando carteiras consecutivas (leve, sem spans).

    Substitui _build_presence_spans no dashboard — usa operações vetorizadas de
    conjuntos em vez de construir spans Python record-a-record. A chave é
    protocolo+setor para preservar a semântica de saída da carteira/setor,
    mesmo quando o protocolo continua presente em outra divisão.
    """
    if frame.empty or len(available_dates) < 2:
        return []

    finalized: dict[str, int] = {}

    # Pré-indexar carteiras e DataFrames por dia para evitar filtros repetidos.
    keys_by_day: dict[date, set] = {}
    df_by_day: dict[date, pd.DataFrame] = {}
    for day in available_dates:
        day_df = frame.loc[frame["report_day"] == day, ["protocolo", "setor", "atribuicao"]].copy()
        day_df["wallet_key"] = day_df["protocolo"].astype(str) + "|" + day_df["setor"].astype(str)
        keys_by_day[day] = set(day_df["wallet_key"])
        df_by_day[day] = day_df

    for idx in range(1, len(available_dates)):
        prev_day = available_dates[idx - 1]
        curr_day = available_dates[idx]
        curr_keys = keys_by_day[curr_day]
        prev_df = df_by_day[prev_day]

        exited = prev_df[~prev_df["wallet_key"].isin(curr_keys)]
        if exited.empty:
            continue

        for atrib, count in exited.groupby("atribuicao").size().items():
            finalized[atrib] = finalized.get(atrib, 0) + int(count)

    ranked = sorted(finalized.items(), key=lambda x: -x[1])[:10]
    return [{"label": a, "value": v} for a, v in ranked]


def get_dashboard_data(db: Session, filters: AnalyticsFilters) -> dict:
    """KPIs, distribuição por setor/tipo/atribuição e evolução diária de processos ativos."""
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=SPAN_FIELDS)
        current = _snapshot(frame, reference_date)

        total_unique = int(current["protocolo"].nunique()) if not current.empty else 0
        duplicates = 0
        if not current.empty:
            duplicates = int(
                current.groupby("protocolo")["setor"].nunique().loc[lambda series: series > 1].shape[0]
            )

        evolution = []
        if not frame.empty:
            evolution_series = frame.groupby("report_day")["protocolo"].nunique()
            evolution = [{"date": str(day), "value": int(value)} for day, value in evolution_series.items()]

        # Ranking de finalizações: usa diferença de conjuntos entre snapshots consecutivos
        # (muito mais leve que _build_presence_spans que era O(n × grupos) com loops Python)
        finalized_ranking = _finalized_by_attribution(frame, available_dates)

        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "kpis": {
                "total_processos_ativos": total_unique,
                "total_registros_snapshot": int(len(current)),
                "setores_ativos": int(current["setor"].nunique()) if not current.empty else 0,
                "duplicidades_multissetor": duplicates,
            },
            "por_setor": _count_series(current, "setor"),
            "por_tipo": _count_series(current, "tipo"),
            "por_atribuicao": _count_series(current, "atribuicao"),
            "ranking_atribuicoes": _count_series(current, "atribuicao")[:10],
            "ranking_atribuicoes_finalizadas": finalized_ranking,
            "evolucao_diaria": evolution,
        }

    return _cached_response(db, "dashboard", filters, build)


def get_entries_exits_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Fluxo de entradas e saídas por setor entre snapshots consecutivos."""
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=FLOW_FIELDS)
        previous_date = _previous_date(available_dates, reference_date)
        protocol_map = _protocols_by_date_and_sector(frame)
        summary_days = {day for day in (reference_date, previous_date) if day}
        summary_sectors = sorted({setor for (day, setor) in protocol_map.keys() if day in summary_days})
        all_sectors = sorted({setor for (_, setor) in protocol_map.keys()})

        resumo: list[dict] = []
        for setor in summary_sectors:
            current_protocols = protocol_map.get((reference_date, setor), set())
            previous_protocols = protocol_map.get((previous_date, setor), set()) if previous_date else set()
            entradas = len(current_protocols - previous_protocols)
            saidas = len(previous_protocols - current_protocols)
            saldo = len(current_protocols) - len(previous_protocols)
            resumo.append(
                {
                    "setor": setor,
                    "entradas": entradas,
                    "saidas": saidas,
                    "saldo": saldo,
                    "carga_atual": len(current_protocols),
                }
            )

        flow_series = []
        for idx, day in enumerate(available_dates):
            previous_day = available_dates[idx - 1] if idx > 0 else None
            for setor in all_sectors:
                current_protocols = protocol_map.get((day, setor), set())
                previous_protocols = protocol_map.get((previous_day, setor), set()) if previous_day else set()
                flow_series.append(
                    {
                        "date": str(day),
                        "setor": setor,
                        "entradas": len(current_protocols - previous_protocols) if previous_day else len(current_protocols),
                        "saidas": len(previous_protocols - current_protocols) if previous_day else 0,
                        "saldo": len(current_protocols) - len(previous_protocols) if previous_day else len(current_protocols),
                        "carga": len(current_protocols),
                    }
                )

        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "data_anterior": str(previous_date) if previous_date else None,
            "resumo_setorial": resumo,
            "entradas_por_setor": [{"label": item["setor"], "value": item["entradas"]} for item in resumo],
            "saidas_por_setor": [{"label": item["setor"], "value": item["saidas"]} for item in resumo],
            "saldo_por_setor": [{"label": item["setor"], "value": item["saldo"]} for item in resumo],
            "evolucao_fluxo": flow_series,
        }

    return _cached_response(db, "entries-exits", filters, build)


def get_productivity_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Produtividade por servidor: produzidos (saíram da carteira), entradas, saldo e ranking do período."""
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=ASSIGNMENT_FIELDS)
        previous_date = _previous_date(available_dates, reference_date)
        assignment_map = _assignments_by_date_and_atribuicao(frame)

        evolution = []
        period_totals: dict[str, dict[str, float | int]] = {}
        for idx, day in enumerate(available_dates):
            previous_day = available_dates[idx - 1] if idx > 0 else None
            current_attributions = {atribuicao for (map_day, atribuicao) in assignment_map.keys() if map_day == day}
            previous_attributions = (
                {atribuicao for (map_day, atribuicao) in assignment_map.keys() if map_day == previous_day}
                if previous_day
                else set()
            )
            tracked_attributions = sorted(current_attributions | previous_attributions)

            for atribuicao in tracked_attributions:
                current_assignments = assignment_map.get((day, atribuicao), set())
                previous_assignments = assignment_map.get((previous_day, atribuicao), set()) if previous_day else set()
                produzidos = len(previous_assignments - current_assignments) if previous_day else 0
                entradas = len(current_assignments - previous_assignments) if previous_day else len(current_assignments)
                saldo = len(current_assignments) - len(previous_assignments) if previous_day else len(current_assignments)
                carga_anterior = len(previous_assignments)
                carga_atual = len(current_assignments)
                taxa_produtividade = round((produzidos / carga_anterior) * 100, 1) if carga_anterior else 0.0

                evolution.append(
                    {
                        "date": str(day),
                        "atribuicao": atribuicao,
                        "produzidos": produzidos,
                        "entradas": entradas,
                        "saldo": saldo,
                        "carga_anterior": carga_anterior,
                        "carga_atual": carga_atual,
                        "taxa_produtividade": taxa_produtividade,
                    }
                )

                if atribuicao not in period_totals:
                    period_totals[atribuicao] = {
                        "produzidos_periodo": 0,
                        "entradas_periodo": 0,
                        "dias_com_movimento": 0,
                    }
                period_totals[atribuicao]["produzidos_periodo"] += produzidos
                period_totals[atribuicao]["entradas_periodo"] += entradas
                if produzidos or entradas:
                    period_totals[atribuicao]["dias_com_movimento"] += 1

        summary_rows = []
        if reference_date:
            summary_rows = [item for item in evolution if item["date"] == str(reference_date)]
            summary_rows.sort(
                key=lambda item: (
                    -item["produzidos"],
                    -item["taxa_produtividade"],
                    -item["carga_anterior"],
                    item["atribuicao"],
                )
            )

        period_days = max(len(available_dates) - 1, 1)
        ranking_periodo = sorted(
            [
                {
                    "atribuicao": atribuicao,
                    "produzidos_periodo": int(metrics["produzidos_periodo"]),
                    "entradas_periodo": int(metrics["entradas_periodo"]),
                    "dias_com_movimento": int(metrics["dias_com_movimento"]),
                    "media_diaria_producao": round(float(metrics["produzidos_periodo"]) / period_days, 2),
                }
                for atribuicao, metrics in period_totals.items()
            ],
            key=lambda item: (-item["produzidos_periodo"], -item["entradas_periodo"], item["atribuicao"]),
        )

        total_produzido_dia = sum(item["produzidos"] for item in summary_rows)
        total_entradas_dia = sum(item["entradas"] for item in summary_rows)
        carga_atual_total = sum(item["carga_atual"] for item in summary_rows)
        maior_produtor = (
            max(
                summary_rows,
                key=lambda item: (item["produzidos"], item["taxa_produtividade"], -item["carga_atual"]),
            )
            if summary_rows
            else None
        )

        top_chart_attributions = [item["atribuicao"] for item in ranking_periodo[:8] if item["produzidos_periodo"] > 0]
        if not top_chart_attributions:
            top_chart_attributions = [item["atribuicao"] for item in summary_rows[:8]]

        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "data_anterior": str(previous_date) if previous_date else None,
            "criterio_produtividade": (
                "Produção estimada = processos atribuídos no snapshot anterior e ausentes na mesma atribuição "
                "na data de referência."
            ),
            "kpis": {
                "total_produzido_dia": int(total_produzido_dia),
                "total_entradas_dia": int(total_entradas_dia),
                "atribuicoes_monitoradas": int(len(summary_rows)),
                "carga_atual_total": int(carga_atual_total),
            },
            "maior_produtor": maior_produtor,
            "resumo_atribuicoes": summary_rows,
            "producao_por_atribuicao": [
                {"label": item["atribuicao"], "value": int(item["produzidos"])}
                for item in sorted(summary_rows, key=lambda row: (-row["produzidos"], row["atribuicao"]))[:10]
            ],
            "entradas_por_atribuicao": [
                {"label": item["atribuicao"], "value": int(item["entradas"])}
                for item in sorted(summary_rows, key=lambda row: (-row["entradas"], row["atribuicao"]))[:10]
            ],
            "carga_atual_por_atribuicao": [
                {"label": item["atribuicao"], "value": int(item["carga_atual"])}
                for item in sorted(summary_rows, key=lambda row: (-row["carga_atual"], row["atribuicao"]))[:10]
            ],
            "ranking_producao_periodo": ranking_periodo[:15],
            "ranking_producao_periodo_grafico": [
                {"label": item["atribuicao"], "value": int(item["produzidos_periodo"])}
                for item in ranking_periodo[:10]
            ],
            "evolucao_produtividade": [
                item for item in evolution if item["atribuicao"] in top_chart_attributions
            ],
        }

    return _cached_response(db, "productivity", filters, build)


def get_stale_processes_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Processos parados: spans abertos ordenados por dias sem movimentação."""
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(
            db, filters, fields=SPAN_FIELDS, apply_lookback=False
        )
        spans = _build_presence_spans(frame, available_dates)
        open_spans = spans[spans["aberto"]] if not spans.empty else spans
        if open_spans.empty:
            return {
                "data_referencia": str(reference_date) if reference_date else None,
                "contagens": {"mais_de_10": 0, "mais_de_20": 0, "mais_de_30": 0},
                "processos": [],
            }

        process_list = [
            {
                "protocolo": row["protocolo"],
                "setor": row["setor"],
                "atribuicao": row["atribuicao"],
                "tipo": row["tipo"],
                "dias_sem_movimentacao": int(row["duracao_dias"]),
                "entrada_setor": str(row["entrada_setor"]),
            }
            for _, row in open_spans.sort_values("duracao_dias", ascending=False).iterrows()
        ]
        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "contagens": {
                "mais_de_10": len([item for item in process_list if item["dias_sem_movimentacao"] > 10]),
                "mais_de_20": len([item for item in process_list if item["dias_sem_movimentacao"] > 20]),
                "mais_de_30": len([item for item in process_list if item["dias_sem_movimentacao"] > 30]),
            },
            "processos": process_list,
        }

    return _cached_response(db, "stale", filters, build)


def get_multi_sector_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Processos presentes em mais de um setor no mesmo snapshot (possíveis duplicidades)."""
    def build() -> dict:
        search_filters = AnalyticsFilters(
            data_referencia=filters.data_referencia,
            data_inicial=filters.data_inicial,
            data_final=filters.data_final,
            setor=None,
            tipo=filters.tipo,
            atribuicao=filters.atribuicao,
        )
        frame, reference_date, _ = _load_dataframe(db, search_filters, fields=FLOW_FIELDS)
        current = _snapshot(frame, reference_date)
        if current.empty:
            return {"data_referencia": str(reference_date) if reference_date else None, "processos": []}

        grouped = current.groupby("protocolo").agg(setores=("setor", lambda values: sorted(set(values)))).reset_index()
        grouped["quantidade_setores"] = grouped["setores"].apply(len)
        duplicated = grouped[grouped["quantidade_setores"] > 1].sort_values("quantidade_setores", ascending=False)

        if filters.setor:
            duplicated = duplicated[duplicated["setores"].apply(lambda setores: filters.setor.upper() in setores)]

        processes = [
            {
                "protocolo": row["protocolo"],
                "setores": row["setores"],
                "data_relatorio": str(reference_date) if reference_date else None,
            }
            for _, row in duplicated.iterrows()
        ]
        return {"data_referencia": str(reference_date) if reference_date else None, "processos": processes}

    return _cached_response(db, "multi-sector", filters, build)


def get_attributions_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Carteira de atribuições ativas com dias de permanência por setor (usa índice por setor, não global)."""
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(
            db, filters, fields=ATTRIBUTION_FIELDS, apply_lookback=False
        )

        if frame.empty or reference_date is None:
            return {
                "data_referencia": None,
                "items": [],
                "total": 0,
                "total_com_atribuicao": 0,
                "total_sem_atribuicao": 0,
                "max_dias": 0,
            }

        # Índice por setor — cada setor pode ter cadência de upload diferente.
        # Usar datas globais (available_dates) causaria falsos "buracos" para setores
        # que enviam CSV com menos frequência que os demais.
        sector_idx_maps: dict[str, dict] = {}
        for _setor_val in frame["setor"].unique():
            _setor_str = str(_setor_val)
            _setor_dates = sorted(frame[frame["setor"] == _setor_val]["report_day"].unique().tolist())
            sector_idx_maps[_setor_str] = {day: idx for idx, day in enumerate(_setor_dates)}

        ref_snapshot = frame[frame["report_day"] == reference_date]
        multi_sector_protocols: set[str] = set(
            ref_snapshot.groupby("protocolo")["setor"]
            .nunique()
            .loc[lambda s: s > 1]
            .index
        )

        ordered = frame.sort_values(["protocolo", "setor", "atribuicao", "data_relatorio"])
        items: list[dict] = []

        for (protocolo, setor, atribuicao), group in ordered.groupby(
            ["protocolo", "setor", "atribuicao"], sort=False
        ):
            records = group.to_dict(orient="records")
            if not records:
                continue

            last = records[-1]
            last_day = last.get("report_day") or pd.Timestamp(last["data_relatorio"]).date()
            if last_day != reference_date:
                continue

            setor_idx_map = sector_idx_maps.get(str(setor), {})

            start_day = last_day
            for i in range(len(records) - 2, -1, -1):
                curr_day = records[i].get("report_day") or pd.Timestamp(records[i]["data_relatorio"]).date()
                next_day = records[i + 1].get("report_day") or pd.Timestamp(records[i + 1]["data_relatorio"]).date()
                if setor_idx_map.get(next_day, -1) != setor_idx_map.get(curr_day, -2) + 1:
                    break
                start_day = curr_day

            dias = max((reference_date - start_day).days, 0)
            atribuicao_display = None if atribuicao == "Não informado" else atribuicao

            items.append({
                "protocolo": str(protocolo),
                "setor": str(setor),
                "atribuicao": atribuicao_display,
                "tipo": last.get("tipo") or "Não informado",
                "entrada_atribuicao": str(start_day),
                "dias_com_atribuicao": dias,
                "multiplos_setores": str(protocolo) in multi_sector_protocols,
            })

        items.sort(key=lambda x: -x["dias_com_atribuicao"])

        total = len(items)
        total_com = sum(1 for item in items if item["atribuicao"])
        total_sem = total - total_com

        return {
            "data_referencia": str(reference_date),
            "items": items,
            "total": total,
            "total_com_atribuicao": total_com,
            "total_sem_atribuicao": total_sem,
            "max_dias": items[0]["dias_com_atribuicao"] if items else 0,
        }

    return _cached_response(db, "attributions", filters, build)


def get_workload_balance(db: Session, filters: AnalyticsFilters) -> dict:
    """Distribuição de carga entre servidores com comparativo ao snapshot anterior."""

    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=ASSIGNMENT_FIELDS)

        if frame.empty or reference_date is None:
            return {"data_referencia": None, "data_anterior": None, "servidores": [], "stats": {}}

        def carga_na_data(d: "date") -> dict[str, int]:
            sub = frame[(frame["report_day"] == d) & (frame["atribuicao"] != "Não informado")]
            return sub.groupby("atribuicao").size().to_dict()

        current = carga_na_data(reference_date)

        ref_idx = next((i for i, d in enumerate(available_dates) if d == reference_date), -1)
        prev_date = available_dates[ref_idx - 1] if ref_idx > 0 else None
        previous = carga_na_data(prev_date) if prev_date else {}

        if not current:
            return {
                "data_referencia": str(reference_date),
                "data_anterior": str(prev_date) if prev_date else None,
                "servidores": [],
                "stats": {},
            }

        cargas = list(current.values())
        total = sum(cargas)
        n = len(cargas)
        media = total / n if n else 0
        std = (sum((c - media) ** 2 for c in cargas) / n) ** 0.5 if n > 1 else 0.0

        prev_total = sum(previous.values()) if previous else None

        servidores = []
        for atrib, carga in sorted(current.items(), key=lambda x: -x[1]):
            desvio_z = (carga - media) / std if std > 0 else 0.0
            prev = previous.get(atrib)
            delta = (carga - prev) if prev is not None else None

            status = (
                "sobrecarga" if desvio_z > 1.5 else
                "elevada"    if desvio_z > 0.5 else
                "baixa"      if desvio_z < -1.0 else
                "normal"
            )

            servidores.append({
                "atribuicao": str(atrib),
                "carga": carga,
                "pct_total": round(carga / total * 100, 1) if total else 0,
                "desvio_z": round(desvio_z, 2),
                "status": status,
                "carga_anterior": prev,
                "delta": delta,
            })

        return {
            "data_referencia": str(reference_date),
            "data_anterior": str(prev_date) if prev_date else None,
            "servidores": servidores,
            "stats": {
                "total_processos": total,
                "total_servidores": n,
                "media_carga": round(media, 1),
                "desvio_padrao": round(std, 1),
                "max_carga": max(cargas),
                "min_carga": min(cargas),
                "total_processos_anterior": prev_total,
                "delta_total": (total - prev_total) if prev_total is not None else None,
                "em_sobrecarga": sum(1 for s in servidores if s["status"] == "sobrecarga"),
            },
        }

    return _cached_response(db, "workload-balance", filters, build)


def get_server_profile(db: Session, filters: AnalyticsFilters) -> dict:
    """Histórico longitudinal completo de um servidor específico."""

    def build() -> dict:
        if not filters.atribuicao:
            return {"encontrado": False, "atribuicao": None}

        frame, reference_date, available_dates = _load_dataframe(
            db, filters, fields=ASSIGNMENT_FIELDS, apply_lookback=False
        )

        if frame.empty or reference_date is None:
            return {"encontrado": False, "atribuicao": filters.atribuicao}

        carga_por_data = frame.groupby("report_day").size().reset_index(name="carga")
        carga_historica = [
            {"data": str(row["report_day"]), "carga": int(row["carga"])}
            for _, row in carga_por_data.iterrows()
        ]

        carga_atual = int((frame["report_day"] == reference_date).sum())

        protos = frame["protocolo"].unique()
        total_recebidos = int(len(protos))
        total_finalizados = 0
        duracoes: list[int] = []

        for proto in protos:
            pf = frame[frame["protocolo"] == proto]
            last = pf["report_day"].max()
            first = pf["report_day"].min()
            if last != reference_date:
                total_finalizados += 1
                duracoes.append((last - first).days)

        media_permanencia = round(sum(duracoes) / len(duracoes)) if duracoes else None

        return {
            "encontrado": True,
            "atribuicao": str(filters.atribuicao),
            "data_referencia": str(reference_date),
            "carga_atual": carga_atual,
            "total_recebidos": total_recebidos,
            "total_finalizados": total_finalizados,
            "em_aberto": total_recebidos - total_finalizados,
            "media_permanencia_dias": media_permanencia,
            "carga_historica": carga_historica,
        }

    return _cached_response(db, "server-profile", filters, build)


def get_lead_time_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Lead time estimado: tempo médio de permanência dos processos que saíram de cada carteira.

    Usa spans fechados (aberto == False) de _build_presence_spans para calcular
    média, mediana, P90 e distribuição por faixas, agrupados por setor, tipo e
    atribuição.  O indicador depende da qualidade e frequência dos snapshots
    importados — não representa o tempo jurídico/administrativo total.
    """
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(
            db, filters, fields=SPAN_FIELDS, apply_lookback=False
        )
        spans = _build_presence_spans(frame, available_dates)

        if spans.empty:
            return _empty_lead_time(reference_date)

        closed = spans[~spans["aberto"]]
        if closed.empty:
            return _empty_lead_time(reference_date)

        durations = closed["duracao_dias"]

        # --- KPIs globais ---
        kpis = {
            "finalizados": int(len(closed)),
            "media_dias": round(float(durations.mean()), 1),
            "mediana_dias": round(float(durations.median()), 1),
            "p90_dias": round(float(durations.quantile(0.90)), 1),
        }

        # --- Distribuição por faixas ---
        bins = [0, 8, 16, 31, 61, 91, float("inf")]
        labels_faixa = ["0-7", "8-15", "16-30", "31-60", "61-90", "90+"]
        faixas = (
            pd.cut(durations, bins=bins, labels=labels_faixa, right=False)
            .value_counts()
            .reindex(labels_faixa, fill_value=0)
        )
        distribuicao = [{"faixa": label, "quantidade": int(count)} for label, count in faixas.items()]

        # --- Rankings por setor ---
        ranking_setor = _lead_time_ranking(closed, "setor")
        ranking_tipo = _lead_time_ranking(closed, "tipo")
        ranking_atribuicao = _lead_time_ranking(closed, "atribuicao")

        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "snapshots_analisados": len(available_dates),
            "nota_metodologica": (
                "Lead time estimado com base nos spans de presença entre snapshots "
                "consecutivos. Apenas processos que saíram da carteira (spans fechados) "
                "são contabilizados."
            ),
            "kpis": kpis,
            "distribuicao_faixas": distribuicao,
            "ranking_setor": ranking_setor,
            "ranking_tipo": ranking_tipo,
            "ranking_atribuicao": ranking_atribuicao,
            "p90_lookup": {
                "setor": _lead_time_p90_lookup(closed, "setor"),
                "tipo": _lead_time_p90_lookup(closed, "tipo"),
                "global": {"p90_dias": kpis["p90_dias"], "finalizados": kpis["finalizados"]},
            },
        }

    return _cached_response(db, "lead-time", filters, build)


def _lead_time_ranking(closed: pd.DataFrame, group_col: str, top_n: int = 10) -> list[dict]:
    """Calcula média, mediana, P90 e quantidade de spans fechados agrupados por uma coluna."""
    grouped = closed.groupby(group_col)["duracao_dias"]
    stats = grouped.agg(["mean", "median", "count"]).rename(
        columns={"mean": "media", "median": "mediana", "count": "finalizados"}
    )
    stats["p90"] = grouped.quantile(0.90)
    stats = stats.sort_values("media", ascending=False).head(top_n)
    return [
        {
            "label": str(label),
            "media_dias": round(float(row["media"]), 1),
            "mediana_dias": round(float(row["mediana"]), 1),
            "p90_dias": round(float(row["p90"]), 1),
            "finalizados": int(row["finalizados"]),
        }
        for label, row in stats.iterrows()
    ]


def _lead_time_p90_lookup(closed: pd.DataFrame, group_col: str) -> dict[str, dict]:
    """Mapa completo de P90 por grupo, usado por analytics derivados como risk-score."""
    grouped = closed.groupby(group_col)["duracao_dias"]
    counts = grouped.count()
    p90s = grouped.quantile(0.90)
    return {
        str(label): {
            "p90_dias": round(float(p90s.loc[label]), 1),
            "finalizados": int(counts.loc[label]),
        }
        for label in p90s.index
    }


def _empty_lead_time(reference_date: date | None) -> dict:
    """Resposta padrão quando não há spans fechados para calcular lead time."""
    return {
        "data_referencia": str(reference_date) if reference_date else None,
        "snapshots_analisados": 0,
        "nota_metodologica": (
            "Lead time estimado com base nos spans de presença entre snapshots "
            "consecutivos. Apenas processos que saíram da carteira (spans fechados) "
            "são contabilizados."
        ),
        "kpis": {
            "finalizados": 0,
            "media_dias": 0,
            "mediana_dias": 0,
            "p90_dias": 0,
        },
        "distribuicao_faixas": [
            {"faixa": f, "quantidade": 0}
            for f in ["0-7", "8-15", "16-30", "31-60", "61-90", "90+"]
        ],
        "ranking_setor": [],
        "ranking_tipo": [],
        "ranking_atribuicao": [],
        "p90_lookup": {"setor": {}, "tipo": {}, "global": {"p90_dias": 0, "finalizados": 0}},
    }


# ─────────────────────────────────────────────────────────────────────────────
# FASE 4 — Forecasting / Tendências estimadas
# ─────────────────────────────────────────────────────────────────────────────

def _linear_trend(values: list[float]) -> tuple[float, float]:
    """Regressão linear simples (OLS). Retorna (slope por passo, intercept).

    Implementação direta sem numpy — evita dependência extra e é suficiente
    para as poucas dezenas de pontos usados nas tendências.
    """
    n = len(values)
    if n < 2:
        return 0.0, float(values[-1]) if values else 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    if ss_xx == 0:
        return 0.0, y_mean
    slope = ss_xy / ss_xx
    return slope, y_mean - slope * x_mean


def _round_forecast(value: float) -> int:
    """Arredonda projeções para evitar falsa precisão numérica."""
    v = max(0.0, value)
    if v > 1000:
        return int(round(v / 100) * 100)
    if v > 200:
        return int(round(v / 50) * 50)
    if v > 50:
        return int(round(v / 10) * 10)
    return int(round(v / 5) * 5)


def _empty_forecast(reference_date: date | None) -> dict:
    """Resposta padrão quando o histórico é insuficiente para calcular tendências."""
    return {
        "data_referencia": str(reference_date) if reference_date else None,
        "snapshots_analisados": 0,
        "nota": "Histórico insuficiente para calcular tendências (mínimo 4 snapshots).",
        "volume": None,
        "setores": [],
        "criticos": None,
    }


def get_forecast_data(db: Session, filters: AnalyticsFilters) -> dict:
    """Tendências estimadas de volume ativo, saldo setorial e processos em envelhecimento.

    Usa regressão linear simples (OLS) sobre os snapshots disponíveis na janela de
    análise (padrão: 120 dias). Os resultados são *estimativas* baseadas no ritmo
    atual — não são previsões determinísticas. Apresentar sempre com linguagem
    cautelosa: "se o ritmo atual se mantiver".
    """
    _MIN_SNAPSHOTS = 4
    _WINDOW = 30  # máx. snapshots recentes usados na regressão de volume

    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(
            db, filters, fields=FLOW_FIELDS
        )

        if frame.empty or len(available_dates) < _MIN_SNAPSHOTS:
            return _empty_forecast(reference_date)

        # ── 1. Volume ativo: tendência ────────────────────────────────────
        volume_by_day = (
            frame.groupby("report_day")["protocolo"]
            .nunique()
            .reindex(available_dates, fill_value=0)
        )
        window_dates = available_dates[-_WINDOW:]
        # Intervalo médio da janela usada no modelo — converte slope "por passo" em "por dia"
        window_span = (window_dates[-1] - window_dates[0]).days
        avg_days = max(1.0, window_span / (len(window_dates) - 1))
        volumes = [int(volume_by_day[d]) for d in window_dates]
        vol_slope, _ = _linear_trend(volumes)

        # slope por snapshot → por dia
        daily_slope = vol_slope / avg_days
        current_vol = volumes[-1]
        vol_15 = _round_forecast(current_vol + daily_slope * 15)
        vol_30 = _round_forecast(current_vol + daily_slope * 30)

        if daily_slope > 3:
            vol_trend = "crescendo"
        elif daily_slope < -3:
            vol_trend = "reduzindo"
        else:
            vol_trend = "estavel"

        # ── 2. Tendência de saldo por setor ──────────────────────────────
        protocol_map = _protocols_by_date_and_sector(frame)

        # Pré-indexar setores por dia para evitar varredura completa a cada passo
        sectors_by_day: dict[date, set] = {}
        for (day, setor) in protocol_map:
            sectors_by_day.setdefault(day, set()).add(setor)

        sector_daily_deltas: dict[str, list[float]] = {}
        for prev_day, curr_day in zip(available_dates[:-1], available_dates[1:]):
            days_gap = max(1, (curr_day - prev_day).days)
            all_sectors = sectors_by_day.get(prev_day, set()) | sectors_by_day.get(curr_day, set())
            for setor in all_sectors:
                curr_n = len(protocol_map.get((curr_day, setor), set()))
                prev_n = len(protocol_map.get((prev_day, setor), set()))
                sector_daily_deltas.setdefault(setor, []).append(
                    (curr_n - prev_n) / days_gap
                )

        recent_transitions = min(len(available_dates) - 1, 21)
        sector_trends_result: list[dict] = []
        for setor, deltas in sector_daily_deltas.items():
            recent = deltas[-recent_transitions:]
            avg_delta = sum(recent) / len(recent) if recent else 0.0
            carga_atual = len(protocol_map.get((available_dates[-1], setor), set()))
            carga_30d = _round_forecast(carga_atual + avg_delta * 30)

            if avg_delta > 1.0:
                setor_trend = "acumulando"
            elif avg_delta < -1.0:
                setor_trend = "resolvendo"
            else:
                setor_trend = "estavel"

            sector_trends_result.append({
                "setor": setor,
                "carga_atual": carga_atual,
                "variacao_diaria_media": round(avg_delta, 1),
                "tendencia": setor_trend,
                "estimado_30d": carga_30d,
            })

        sector_trends_result.sort(key=lambda x: abs(x["variacao_diaria_media"]), reverse=True)

        # ── 3. Processos em envelhecimento ───────────────────────────────
        # Conta apenas presenças consecutivas que chegam ao snapshot atual.
        # Isso evita considerar processos que apareceram muito no passado, mas já saíram.
        presence_by_day: dict[date, set[tuple[str, str]]] = {}
        for day, day_frame in frame.groupby("report_day"):
            presence_by_day[day] = {
                (str(row.protocolo), str(row.setor))
                for row in day_frame[["protocolo", "setor"]].itertuples(index=False)
            }

        latest_day = available_dates[-1]
        latest_keys = presence_by_day.get(latest_day, set())
        streak_days: list[float] = []
        for key in latest_keys:
            streak = 0
            for day in reversed(available_dates):
                if key not in presence_by_day.get(day, set()):
                    break
                streak += 1
            streak_days.append(streak * avg_days)

        current_30_est = sum(1 for days in streak_days if days >= 30)
        will_cross_30_in_15d = sum(1 for days in streak_days if 15 <= days < 30)
        estimated_critical_15d = _round_forecast(current_30_est + will_cross_30_in_15d * 0.7)

        snapshots_used = len(window_dates)

        return {
            "data_referencia": str(reference_date) if reference_date else None,
            "snapshots_analisados": snapshots_used,
            "nota": (
                f"Calculado com os últimos {snapshots_used} snapshots. "
                "Se o ritmo atual se mantiver."
            ),
            "volume": {
                "atual": current_vol,
                "estimado_15d": vol_15,
                "estimado_30d": vol_30,
                "tendencia": vol_trend,
                "variacao_diaria_media": round(daily_slope, 1),
            },
            "setores": sector_trends_result,
            "criticos": {
                "atual_estimado": current_30_est,
                "estimado_15d": estimated_critical_15d,
                "em_risco_15d": will_cross_30_in_15d,
                "range_20_30": will_cross_30_in_15d,
                "nota": (
                    "Estimativa baseada em presenças consecutivas até o snapshot atual. "
                    "Para dados exatos, consulte a página Atribuições."
                ),
            },
        }

    return _cached_response(db, "forecast", filters, build)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 5 — Score de Risco por processo
# ─────────────────────────────────────────────────────────────────────────────

def get_risk_scores(db: Session, filters: AnalyticsFilters) -> dict:
    """Score de risco composto por processo ativo no snapshot de referência.

    Combina quatro fatores ponderados:
      • Tempo absoluto no setor   (peso _RISK_W_ABS)
      • Tempo relativo ao P90     (peso _RISK_W_REL)   — com fallback setor→tipo→global
      • Ausência de atribuição    (peso _RISK_W_UNASSIGNED)
      • Presença em múltiplos setores (peso _RISK_W_MULTI)
    Aplicados de um multiplicador de tendência setorial (1.2 / 1.0 / 0.85).

    score = min((W_ABS×D_abs + W_REL×D_rel + W_UNASSIGNED×A + W_MULTI×V) × T, 1.0)
    D_abs = min(dias / _RISK_ABS_NORM, 1.0)
    D_rel = min(dias / p90, 2.0) / 2.0  → ∈ [0, 1.0]

    O score é sobre o **processo**, não sobre o servidor atribuído.
    Todos os pesos e thresholds são configuráveis via variáveis de ambiente.

    Nota: P90 setor+tipo não está disponível nesta versão (exigiria computação
    adicional de spans). Hierarquia atual: setor → tipo → global.
    """

    def build() -> dict:
        # ── Dados base: processos ativos com streak consecutivo até hoje ──
        stale = get_stale_processes_data(db, filters)
        processos = stale.get("processos", [])
        reference_date = stale.get("data_referencia")

        if not processos:
            return _empty_risk(reference_date)

        # ── P90 lookup com fallback: setor → tipo → global ────────────────
        lt = get_lead_time_data(db, filters)
        p90_lookup = lt.get("p90_lookup") or {}
        setor_source = p90_lookup.get("setor") or {
            item["label"]: item for item in lt.get("ranking_setor", [])
        }
        tipo_source = p90_lookup.get("tipo") or {
            item["label"]: item for item in lt.get("ranking_tipo", [])
        }
        setor_p90: dict[str, float] = {
            label: float(item["p90_dias"])
            for label, item in setor_source.items()
            if item.get("finalizados", 0) >= _RISK_MIN_SAMPLE and item.get("p90_dias", 0) > 0
        }
        tipo_p90: dict[str, float] = {
            label: float(item["p90_dias"])
            for label, item in tipo_source.items()
            if item.get("finalizados", 0) >= _RISK_MIN_SAMPLE and item.get("p90_dias", 0) > 0
        }
        global_stats = p90_lookup.get("global") or lt.get("kpis", {})
        global_p90: float | None = (
            float(global_stats.get("p90_dias"))
            if global_stats.get("finalizados", 0) >= _RISK_MIN_SAMPLE and global_stats.get("p90_dias", 0) > 0
            else None
        )
        lt_coverage = bool(setor_p90 or tipo_p90 or global_p90)

        def _lookup_p90(setor: str, tipo: str) -> tuple[float | None, str | None]:
            """Retorna (p90, fonte) com fallback setor→tipo→global."""
            if v := setor_p90.get(setor):
                return v, "setor"
            if v := tipo_p90.get(tipo or ""):
                return v, "tipo"
            if global_p90:
                return global_p90, "global"
            return None, None

        # ── Protocolos em múltiplos setores ───────────────────────────────
        multi = get_multi_sector_data(db, filters)
        multi_protos: set[str] = {p["protocolo"] for p in multi.get("processos", [])}

        # ── Tendência setorial (do forecast) ──────────────────────────────
        fc = get_forecast_data(db, filters)
        sector_trend: dict[str, str] = {
            s["setor"]: s["tendencia"] for s in fc.get("setores", [])
        }
        trend_mult = {
            "acumulando": _RISK_TREND_UP,
            "estavel":    _RISK_TREND_STABLE,
            "resolvendo": _RISK_TREND_DOWN,
        }

        # ── Calcular score por processo ───────────────────────────────────
        contagens: dict[str, int] = {"critico": 0, "elevado": 0, "moderado": 0, "normal": 0}
        scored: list[dict] = []

        for proc in processos:
            protocolo = str(proc["protocolo"])
            setor     = str(proc.get("setor", ""))
            tipo      = str(proc.get("tipo") or "")
            atribuicao = proc.get("atribuicao")
            dias      = int(proc.get("dias_sem_movimentacao", 0))

            # Fator 1 — tempo absoluto (normalizado a _RISK_ABS_NORM dias)
            f_abs = min(dias / _RISK_ABS_NORM, 1.0)

            # Fator 2 — tempo relativo ao P90 histórico (hierarquia setor→tipo→global)
            p90, p90_fonte = _lookup_p90(setor, tipo)
            if p90 and p90 > 0:
                p90_efetivo = max(p90, _RISK_MIN_P90_DAYS)
                f_rel = min(dias / p90_efetivo, 2.0) / 2.0
                if p90_efetivo > p90:
                    p90_detalhe = (
                        f"{dias}d vs P90 ({p90_fonte}) de {round(p90)}d "
                        f"(piso técnico {round(_RISK_MIN_P90_DAYS)}d aplicado)"
                    )
                else:
                    p90_detalhe = f"{dias}d vs P90 ({p90_fonte}) de {round(p90)}d"
            else:
                f_rel = 0.0
                p90_fonte = None
                p90_detalhe = "Sem histórico de lead time para referência"

            # Fator 3 — ausência de atribuição
            sem_atrib = not atribuicao or atribuicao == "Não informado"
            f_unassigned = 1.0 if sem_atrib else 0.0

            # Fator 4 — múltiplos setores
            f_multi = 1.0 if protocolo in multi_protos else 0.0

            # Multiplicador de tendência setorial
            trend = sector_trend.get(setor, "estavel")
            t_mult = trend_mult.get(trend, _RISK_TREND_STABLE)

            # Score final
            base = (
                _RISK_W_ABS        * f_abs +
                _RISK_W_REL        * f_rel +
                _RISK_W_UNASSIGNED * f_unassigned +
                _RISK_W_MULTI      * f_multi
            )
            score = round(min(base * t_mult, 1.0), 3)

            # Nível de risco
            if score >= _RISK_THR_CRITICAL:
                nivel = "critico"
            elif score >= _RISK_THR_HIGH:
                nivel = "elevado"
            elif score >= _RISK_THR_MODERATE:
                nivel = "moderado"
            else:
                nivel = "normal"

            contagens[nivel] += 1

            scored.append({
                "protocolo":    protocolo,
                "setor":        setor,
                "atribuicao":   None if sem_atrib else atribuicao,
                "tipo":         tipo or None,
                "dias_no_setor": dias,
                "entrada_setor": proc.get("entrada_setor"),
                "score":        score,
                "nivel":        nivel,
                "fatores": {
                    "tempo_absoluto": {
                        "contribuicao": round(_RISK_W_ABS * f_abs, 3),
                        "detalhe": f"{dias}d no setor ({round(f_abs * 100)}% do limiar de {_RISK_ABS_NORM}d)",
                    },
                    "tempo_relativo": {
                        "contribuicao": round(_RISK_W_REL * f_rel, 3),
                        "detalhe": p90_detalhe,
                        "p90_fonte": p90_fonte,
                    },
                    "sem_atribuicao": {
                        "contribuicao": round(_RISK_W_UNASSIGNED * f_unassigned, 3),
                        "detalhe": "Sem responsável definido" if sem_atrib else "",
                    },
                    "multiplos_setores": {
                        "contribuicao": round(_RISK_W_MULTI * f_multi, 3),
                        "detalhe": "Tramitando em múltiplos setores" if f_multi else "",
                    },
                    "tendencia_setor": {
                        "multiplicador": t_mult,
                        "detalhe": f"Setor {setor}: {trend}" if trend != "estavel" else "",
                    },
                },
            })

        scored.sort(key=lambda x: -x["score"])

        return {
            "data_referencia":    reference_date,
            "total_analisados":   len(scored),
            "cobertura_lead_time": lt_coverage,
            "nota": (
                "Score calculado sobre o processo — não sobre o servidor. "
                "Valores refletem condições do processo no snapshot atual."
            ),
            "pesos": {
                "tempo_absoluto":   _RISK_W_ABS,
                "tempo_relativo":   _RISK_W_REL,
                "sem_atribuicao":   _RISK_W_UNASSIGNED,
                "multiplos_setores": _RISK_W_MULTI,
            },
            "thresholds": {
                "critico":  _RISK_THR_CRITICAL,
                "elevado":  _RISK_THR_HIGH,
                "moderado": _RISK_THR_MODERATE,
            },
            "contagens": contagens,
            "processos": scored,
        }

    return _cached_response(db, "risk-score", filters, build)


def _empty_risk(reference_date: date | None) -> dict:
    return {
        "data_referencia":    str(reference_date) if reference_date else None,
        "total_analisados":   0,
        "cobertura_lead_time": False,
        "nota":               "Nenhum processo ativo encontrado para os filtros aplicados.",
        "pesos":              {},
        "thresholds":         {},
        "contagens":          {"critico": 0, "elevado": 0, "moderado": 0, "normal": 0},
        "processos":          [],
    }

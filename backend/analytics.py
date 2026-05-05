from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
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


def clear_analytics_cache() -> None:
    with _CACHE_LOCK:
        _ANALYTICS_CACHE.clear()


def _uploads_signature(db: Session) -> tuple[object, ...]:
    total_uploads, latest_upload_id, latest_upload_time = (
        db.query(
            func.count(Upload.id),
            func.max(Upload.id),
            func.max(Upload.data_upload),
        ).one()
    )
    return (
        int(total_uploads or 0),
        int(latest_upload_id or 0),
        latest_upload_time.isoformat() if isinstance(latest_upload_time, datetime) else None,
    )


def _cached_response(
    db: Session,
    cache_name: str,
    filters: AnalyticsFilters | None,
    builder: Callable[[], dict],
) -> dict:
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
    dates = _available_dates(db, filters)
    if not dates:
        return None
    if not filters.data_referencia:
        return dates[-1]
    eligible = [day for day in dates if day <= filters.data_referencia]
    return eligible[-1] if eligible else dates[-1]


def _load_dataframe(
    db: Session,
    filters: AnalyticsFilters,
    fields: Sequence[str] | None = None,
    upto_reference: bool = True,
) -> tuple[pd.DataFrame, date | None, list[date]]:
    reference_date = _resolve_reference_date(db, filters)
    requested_fields = _normalize_fields(fields)

    query = _base_query(db, filters)
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


def get_dashboard_data(db: Session, filters: AnalyticsFilters) -> dict:
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

        spans = _build_presence_spans(frame, available_dates)
        finalized_ranking = []
        if not spans.empty:
            finalized = spans[~spans["aberto"]]
            if not finalized.empty:
                ranking = (
                    finalized.groupby("atribuicao")["protocolo"].count().sort_values(ascending=False).head(10)
                )
                finalized_ranking = [{"label": key, "value": int(value)} for key, value in ranking.items()]

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
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=SPAN_FIELDS)
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
    def build() -> dict:
        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=ATTRIBUTION_FIELDS)

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

        frame, reference_date, available_dates = _load_dataframe(db, filters, fields=ASSIGNMENT_FIELDS)

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

from __future__ import annotations

import unicodedata
from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import MonthlyStat


MONTHLY_INDICATORS = [
    "Processos gerados no per\u00edodo",
    "Processos com tramita\u00e7\u00e3o no per\u00edodo",
    "Processos com andamento fechado na unidade ao final do per\u00edodo",
    "Processos com andamento aberto na unidade ao final do per\u00edodo",
    "Documentos gerados no per\u00edodo",
    "Documentos externos no per\u00edodo",
]

INDICATOR_ENTRY_MAP = {
    "processos_gerados": MONTHLY_INDICATORS[0],
    "processos_tramitacao": MONTHLY_INDICATORS[1],
    "processos_fechados": MONTHLY_INDICATORS[2],
    "processos_abertos": MONTHLY_INDICATORS[3],
    "documentos_gerados": MONTHLY_INDICATORS[4],
    "documentos_externos": MONTHLY_INDICATORS[5],
}

MONTH_NAMES = {
    1: "janeiro",
    2: "fevereiro",
    3: "mar\u00e7o",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

SETOR_OPTIONS = {
    "DIAPE",
    "DICAT",
    "DIJOR",
    "DICAF",
    "DICAF-CHEFIA",
    "DICAF-REPOSICOES",
}


def clean_text(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def canonicalize_indicator(value: object) -> str:
    text = clean_text(value) or ""
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return without_accents.casefold()


INDICATOR_LOOKUP = {canonicalize_indicator(label): label for label in MONTHLY_INDICATORS}


def normalize_setor(value: object) -> str:
    text = (clean_text(value) or "").replace("_", "-").upper()
    if text not in SETOR_OPTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Setor mensal invalido: {value}.")
    return text


def normalize_indicator(value: object) -> str:
    text = clean_text(value)
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Indicador mensal nao informado.")

    normalized = INDICATOR_LOOKUP.get(canonicalize_indicator(text))
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Indicador mensal invalido: {text}.",
        )
    return normalized


def parse_int(value: object) -> int:
    text = clean_text(value)
    if not text:
        return 0

    normalized = text.replace(".", "").replace(",", ".")
    return int(float(normalized))


def build_period_fields(
    ano: int,
    num_mes: int,
    mes: object | None = None,
    mes_ano: object | None = None,
) -> dict[str, object]:
    month_number = int(num_mes)
    if month_number not in MONTH_NAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes invalido para indicador mensal.")

    year_number = int(ano)
    month_name = clean_text(mes) or MONTH_NAMES[month_number]
    month_year_label = clean_text(mes_ano) or f"{month_name[:3].lower()}/{str(year_number)[-2:]}"

    return {
        "ano": year_number,
        "num_mes": month_number,
        "mes": month_name,
        "mes_ano": month_year_label,
        "periodo": date(year_number, month_number, 1),
    }


def upsert_monthly_stat(
    db: Session,
    *,
    setor: object,
    indicador: object,
    valor: object,
    ano: object,
    num_mes: object,
    mes: object | None = None,
    mes_ano: object | None = None,
) -> str:
    normalized_setor = normalize_setor(setor)
    normalized_indicator = normalize_indicator(indicador)
    numeric_value = parse_int(valor)
    period_fields = build_period_fields(int(ano), int(num_mes), mes=mes, mes_ano=mes_ano)

    existing = (
        db.query(MonthlyStat)
        .filter(
            MonthlyStat.setor == normalized_setor,
            MonthlyStat.indicador == normalized_indicator,
            MonthlyStat.ano == period_fields["ano"],
            MonthlyStat.num_mes == period_fields["num_mes"],
        )
        .first()
    )

    if existing:
        existing.valor = numeric_value
        existing.mes = period_fields["mes"]
        existing.mes_ano = period_fields["mes_ano"]
        existing.periodo = period_fields["periodo"]
        action = "updated"
    else:
        db.add(
            MonthlyStat(
                setor=normalized_setor,
                indicador=normalized_indicator,
                valor=numeric_value,
                mes=period_fields["mes"],
                mes_ano=period_fields["mes_ano"],
                num_mes=period_fields["num_mes"],
                ano=period_fields["ano"],
                periodo=period_fields["periodo"],
            )
        )
        action = "created"

    db.flush()
    return action


def import_monthly_stats_csv(db: Session, file_bytes: bytes) -> dict[str, int]:
    dataframe = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            dataframe = pd.read_csv(BytesIO(file_bytes), sep=";", dtype=str, keep_default_na=False, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue

    if dataframe is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao foi possivel ler o CSV de indicadores mensais.",
        )

    required_columns = {"setor", "indicador", "valor", "mes_ano", "mes", "num_mes", "ano"}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV mensal sem colunas obrigatorias: {', '.join(sorted(missing_columns))}.",
        )

    imported = 0
    updated = 0
    total = 0
    for row in dataframe.to_dict(orient="records"):
        action = upsert_monthly_stat(
            db,
            setor=row.get("setor"),
            indicador=row.get("indicador"),
            valor=row.get("valor"),
            ano=row.get("ano"),
            num_mes=row.get("num_mes"),
            mes=row.get("mes"),
            mes_ano=row.get("mes_ano"),
        )
        total += 1
        if action == "created":
            imported += 1
        else:
            updated += 1

    db.commit()
    return {"imported": imported, "updated": updated, "total": total}


def upsert_month_entry(db: Session, payload: dict[str, object]) -> dict[str, int]:
    existing_records = (
        db.query(MonthlyStat)
        .filter(
            MonthlyStat.setor == normalize_setor(payload["setor"]),
            MonthlyStat.ano == int(payload["ano"]),
            MonthlyStat.num_mes == int(payload["num_mes"]),
        )
        .count()
    )
    if existing_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ja existem indicadores cadastrados para este setor e periodo. Use a edicao por linha no historico.",
        )

    imported = 0
    updated = 0
    total = 0

    for field_name, indicator in INDICATOR_ENTRY_MAP.items():
        action = upsert_monthly_stat(
            db,
            setor=payload["setor"],
            indicador=indicator,
            valor=payload[field_name],
            ano=payload["ano"],
            num_mes=payload["num_mes"],
        )
        total += 1
        if action == "created":
            imported += 1
        else:
            updated += 1

    db.commit()
    return {"imported": imported, "updated": updated, "total": total}


def update_monthly_stat_value(db: Session, stat_id: int, valor: object) -> MonthlyStat:
    monthly_stat = db.query(MonthlyStat).filter(MonthlyStat.id == stat_id).first()
    if not monthly_stat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Indicador mensal nao encontrado.")

    monthly_stat.valor = parse_int(valor)
    db.commit()
    db.refresh(monthly_stat)
    return monthly_stat

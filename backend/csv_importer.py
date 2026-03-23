from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from .models import Processo, Upload


SETORES = [
    "DIAPE",
    "DICAT",
    "DIJOR",
    "DICAF",
    "DICAF-CHEFIA",
    "DICAF-REPOSICOES",
]

CSV_FIELD_MAP = {
    "ID": "source_row_id",
    "Protocolo": "protocolo",
    "Atribuicao": "atribuicao",
    "Tipo": "tipo",
    "Especificacao": "especificacao",
    "Ponto_Controle": "ponto_controle",
    "Data_Autuacao": "data_autuacao",
    "Data_Recebimento": "data_recebimento",
    "Data_Envio": "data_envio",
    "Unidade_Envio": "unidade_envio",
    "Observacoes": "observacoes",
}

DATE_FIELDS = {"data_autuacao", "data_recebimento", "data_envio"}
FILENAME_PATTERN = re.compile(r"ListaProcessos_SEIPro_(?P<data>\d{8})_(?P<setor>[a-z-]+)\.csv$", re.IGNORECASE)


def normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-" or text.lower() == "nan":
        return None
    return text


def parse_csv_date(value: object) -> date | None:
    text = normalize_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(
                BytesIO(file_bytes),
                sep=";",
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível ler o arquivo CSV. Verifique a codificação do arquivo exportado do SEI.")


def prepare_dataframe(raw_df: pd.DataFrame, setor: str, data_relatorio: date) -> pd.DataFrame:
    frame = raw_df.copy()
    for csv_column in CSV_FIELD_MAP:
        if csv_column not in frame.columns:
            frame[csv_column] = None

    prepared = frame[list(CSV_FIELD_MAP.keys())].rename(columns=CSV_FIELD_MAP)
    prepared["setor"] = setor
    prepared["data_relatorio"] = data_relatorio

    for column in prepared.columns:
        if column in DATE_FIELDS:
            prepared[column] = prepared[column].apply(parse_csv_date)
        else:
            prepared[column] = prepared[column].apply(normalize_text)

    prepared = prepared.dropna(subset=["protocolo"]).drop_duplicates(subset=["protocolo"], keep="first")
    return prepared


def import_csv_snapshot(
    db: Session,
    file_bytes: bytes,
    filename: str,
    setor: str,
    data_relatorio: date,
) -> dict:
    setor = setor.upper().strip()
    if setor not in SETORES:
        raise ValueError("Setor inválido.")

    file_hash = compute_file_hash(file_bytes)
    existing_same_file = (
        db.query(Upload)
        .filter(
            Upload.setor == setor,
            Upload.data_relatorio == data_relatorio,
            Upload.file_hash == file_hash,
        )
        .first()
    )
    if existing_same_file:
        return {
            "status": "duplicate",
            "message": "Este relatório já havia sido importado anteriormente.",
            "setor": setor,
            "data_relatorio": data_relatorio,
            "original_filename": filename,
            "total_registros": existing_same_file.total_records,
            "substituiu_snapshot_anterior": False,
        }

    raw_df = _read_csv(file_bytes)
    prepared = prepare_dataframe(raw_df, setor=setor, data_relatorio=data_relatorio)
    if prepared.empty:
        raise ValueError("O arquivo não possui processos válidos para importação.")

    existing_uploads = db.query(Upload).filter(Upload.setor == setor, Upload.data_relatorio == data_relatorio).all()
    replaced_snapshot = bool(existing_uploads)
    if replaced_snapshot:
        db.query(Processo).filter(
            Processo.setor == setor,
            Processo.data_relatorio == data_relatorio,
        ).delete(synchronize_session=False)
        db.query(Upload).filter(Upload.setor == setor, Upload.data_relatorio == data_relatorio).delete(
            synchronize_session=False
        )
        db.flush()

    upload = Upload(
        setor=setor,
        data_relatorio=data_relatorio,
        original_filename=filename,
        file_hash=file_hash,
        total_records=int(len(prepared)),
    )
    db.add(upload)
    db.flush()

    processos = [
        Processo(
            source_row_id=row.get("source_row_id"),
            protocolo=row["protocolo"],
            atribuicao=row.get("atribuicao"),
            tipo=row.get("tipo"),
            especificacao=row.get("especificacao"),
            ponto_controle=row.get("ponto_controle"),
            data_autuacao=row.get("data_autuacao"),
            data_recebimento=row.get("data_recebimento"),
            data_envio=row.get("data_envio"),
            unidade_envio=row.get("unidade_envio"),
            observacoes=row.get("observacoes"),
            setor=setor,
            data_relatorio=data_relatorio,
            upload_id=upload.id,
        )
        for row in prepared.to_dict(orient="records")
    ]
    db.add_all(processos)
    db.commit()

    action = "substituído" if replaced_snapshot else "importado"
    return {
        "status": "replaced" if replaced_snapshot else "imported",
        "message": f"Relatório {action} com sucesso.",
        "setor": setor,
        "data_relatorio": data_relatorio,
        "original_filename": filename,
        "total_registros": len(processos),
        "substituiu_snapshot_anterior": replaced_snapshot,
    }


def infer_metadata_from_filename(filename: str) -> tuple[str | None, date | None]:
    match = FILENAME_PATTERN.search(filename)
    if not match:
        return None, None
    raw_setor = match.group("setor").replace("_", "-").upper()
    raw_date = match.group("data")
    report_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
    return raw_setor, report_date


def should_auto_import() -> bool:
    return os.getenv("AUTO_IMPORT_SAMPLE_DATA", "true").lower() in {"1", "true", "yes", "on"}


def bootstrap_workspace_csvs(db: Session) -> list[dict]:
    if not should_auto_import():
        return []

    project_root = Path(__file__).resolve().parent.parent
    results: list[dict] = []
    for csv_file in sorted(project_root.glob("ListaProcessos_SEIPro_*.csv")):
        setor, report_date = infer_metadata_from_filename(csv_file.name)
        if not setor or not report_date or setor not in SETORES:
            continue
        result = import_csv_snapshot(
            db=db,
            file_bytes=csv_file.read_bytes(),
            filename=csv_file.name,
            setor=setor,
            data_relatorio=report_date,
        )
        results.append(result)
    return results

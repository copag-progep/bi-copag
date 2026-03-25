from __future__ import annotations

import re
import unicodedata
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Processo, SeiUser


HEADER_ALIASES = {
    "nome": "nome",
    "nome_sei": "nome_sei",
    "nome sei": "nome_sei",
    "usuario_sei": "usuario_sei",
    "usuario sei": "usuario_sei",
    "usuário_sei": "usuario_sei",
    "usuário sei": "usuario_sei",
}


def clean_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-" or text.lower() == "nan":
        return None
    return text


def normalize_identity(value: object) -> str | None:
    text = clean_value(value)
    if not text:
        return None

    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    return normalized or None


def normalize_header(value: object) -> str:
    text = clean_value(value) or ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").casefold()
    return normalized


def apply_mapping_keys(nome: object, nome_sei: object, usuario_sei: object) -> dict[str, str | None]:
    cleaned_nome = clean_value(nome)
    if not cleaned_nome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cada usuario SEI precisa ter um nome principal informado.",
        )

    cleaned_nome_sei = clean_value(nome_sei)
    cleaned_usuario_sei = clean_value(usuario_sei)

    return {
        "nome": cleaned_nome,
        "nome_sei": cleaned_nome_sei,
        "usuario_sei": cleaned_usuario_sei,
        "nome_key": normalize_identity(cleaned_nome),
        "nome_sei_key": normalize_identity(cleaned_nome_sei),
        "usuario_sei_key": normalize_identity(cleaned_usuario_sei),
    }


def build_sei_user_lookup(db: Session) -> dict[str, str]:
    lookup: dict[str, str] = {}
    users = db.query(SeiUser).order_by(SeiUser.nome.asc()).all()
    for user in users:
        for token in (user.nome_key, user.nome_sei_key, user.usuario_sei_key):
            if token:
                lookup[token] = user.nome
    return lookup


def resolve_atribuicao_canonica(value: object, lookup: dict[str, str]) -> str | None:
    cleaned = clean_value(value)
    if not cleaned:
        return None

    return lookup.get(normalize_identity(cleaned) or "", cleaned)


def sync_processo_atribuicoes(db: Session) -> int:
    lookup = build_sei_user_lookup(db)
    processos = db.query(Processo).all()
    changed = 0

    for processo in processos:
        normalized = resolve_atribuicao_canonica(processo.atribuicao, lookup)
        if processo.atribuicao_normalizada != normalized:
            processo.atribuicao_normalizada = normalized
            changed += 1

    if changed:
        db.commit()

    return changed


def _find_matching_users(db: Session, payload: dict[str, str | None]) -> list[SeiUser]:
    filters = [SeiUser.nome_key == payload["nome_key"]]
    if payload["nome_sei_key"]:
        filters.append(SeiUser.nome_sei_key == payload["nome_sei_key"])
    if payload["usuario_sei_key"]:
        filters.append(SeiUser.usuario_sei_key == payload["usuario_sei_key"])

    if not filters:
        return []

    return db.query(SeiUser).filter(or_(*filters)).all()


def upsert_sei_user(db: Session, nome: object, nome_sei: object, usuario_sei: object) -> tuple[str, SeiUser]:
    payload = apply_mapping_keys(nome, nome_sei, usuario_sei)
    matches = _find_matching_users(db, payload)

    if len({user.id for user in matches}) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encontrado conflito entre registros de usuarios SEI. Ajuste o DE-PARA antes de continuar.",
        )

    if matches:
        user = matches[0]
        user.nome = payload["nome"]
        user.nome_sei = payload["nome_sei"]
        user.usuario_sei = payload["usuario_sei"]
        user.nome_key = payload["nome_key"]
        user.nome_sei_key = payload["nome_sei_key"]
        user.usuario_sei_key = payload["usuario_sei_key"]
        action = "updated"
    else:
        user = SeiUser(**payload)
        db.add(user)
        action = "created"

    db.flush()
    return action, user


def delete_sei_user(db: Session, sei_user_id: int) -> str:
    user = db.query(SeiUser).filter(SeiUser.id == sei_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario SEI nao encontrado.")

    name = user.nome
    db.delete(user)
    db.commit()
    return name


def _read_mapping_dataframe(filename: str, file_bytes: bytes) -> pd.DataFrame:
    lower_name = filename.lower()
    buffer = BytesIO(file_bytes)

    if lower_name.endswith(".csv"):
        for separator in (";", ","):
            buffer.seek(0)
            try:
                return pd.read_csv(buffer, sep=separator, dtype=str, keep_default_na=False)
            except Exception:
                continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao foi possivel ler o CSV enviado para o DE-PARA.",
        )

    if lower_name.endswith(".xlsx"):
        return pd.read_excel(buffer, dtype=str, engine="openpyxl")

    if lower_name.endswith(".xls"):
        return pd.read_excel(buffer, dtype=str, engine="xlrd")

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Envie um arquivo .xls, .xlsx ou .csv com a tabela de usuarios SEI.",
    )


def import_sei_users_file(db: Session, filename: str, file_bytes: bytes) -> dict[str, int]:
    frame = _read_mapping_dataframe(filename, file_bytes)
    if frame.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A planilha enviada esta vazia.")

    renamed_columns = {}
    for column in frame.columns:
        header = normalize_header(column)
        if header in HEADER_ALIASES:
            renamed_columns[column] = HEADER_ALIASES[header]

    prepared = frame.rename(columns=renamed_columns)
    if "nome" not in prepared.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A planilha precisa conter a coluna NOME.",
        )

    imported = 0
    updated = 0
    total = 0

    for record in prepared.to_dict(orient="records"):
        if not clean_value(record.get("nome")):
            continue

        action, _ = upsert_sei_user(
            db,
            nome=record.get("nome"),
            nome_sei=record.get("nome_sei"),
            usuario_sei=record.get("usuario_sei"),
        )
        total += 1
        if action == "created":
            imported += 1
        else:
            updated += 1

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma linha valida foi encontrada na planilha enviada.",
        )

    db.commit()
    sync_processo_atribuicoes(db)
    return {"imported": imported, "updated": updated, "total": total}

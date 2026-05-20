"""DE-PARA de servidores do SEI: normaliza nomes, resolve atribuições canônicas e sincroniza processos."""
from __future__ import annotations

import re
import unicodedata
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session, selectinload

from .models import Processo, SeiUser, SeiUserAlias


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
    users = db.query(SeiUser).options(selectinload(SeiUser.aliases)).order_by(SeiUser.nome.asc()).all()
    for user in users:
        for token in (user.nome_key, user.nome_sei_key, user.usuario_sei_key):
            if token:
                lookup[token] = user.nome
        for alias in user.aliases:
            if alias.alias_key:
                lookup[alias.alias_key] = user.nome
    return lookup


def resolve_atribuicao_canonica(value: object, lookup: dict[str, str]) -> str | None:
    cleaned = clean_value(value)
    if not cleaned:
        return None

    return lookup.get(normalize_identity(cleaned) or "", cleaned)


def sync_processo_atribuicoes(db: Session) -> int:
    lookup = build_sei_user_lookup(db)
    changed = 0

    result = db.execute(
        update(Processo)
        .where(Processo.atribuicao.is_(None), Processo.atribuicao_normalizada.is_not(None))
        .values(atribuicao_normalizada=None)
        .execution_options(synchronize_session=False)
    )
    changed += result.rowcount

    distinct_rows = (
        db.query(Processo.atribuicao)
        .filter(Processo.atribuicao.is_not(None))
        .distinct()
        .all()
    )

    for (atribuicao,) in distinct_rows:
        normalized = resolve_atribuicao_canonica(atribuicao, lookup)
        if normalized is None:
            result = db.execute(
                update(Processo)
                .where(Processo.atribuicao == atribuicao, Processo.atribuicao_normalizada.is_not(None))
                .values(atribuicao_normalizada=None)
                .execution_options(synchronize_session=False)
            )
        else:
            result = db.execute(
                update(Processo)
                .where(
                    Processo.atribuicao == atribuicao,
                    or_(Processo.atribuicao_normalizada.is_(None), Processo.atribuicao_normalizada != normalized),
                )
                .values(atribuicao_normalizada=normalized)
                .execution_options(synchronize_session=False)
            )
        changed += result.rowcount

    if changed:
        db.commit()

    return changed


def needs_processo_atribuicoes_sync(db: Session) -> bool:
    return (
        db.query(Processo.id)
        .filter(
            Processo.atribuicao.is_not(None),
            Processo.atribuicao_normalizada.is_(None),
        )
        .first()
        is not None
    )


def _find_matching_users(db: Session, payload: dict[str, str | None]) -> list[SeiUser]:
    filters = [SeiUser.nome_key == payload["nome_key"]]
    if payload["nome_sei_key"]:
        filters.append(SeiUser.nome_sei_key == payload["nome_sei_key"])
    if payload["usuario_sei_key"]:
        filters.append(SeiUser.usuario_sei_key == payload["usuario_sei_key"])

    if not filters:
        return []

    return db.query(SeiUser).filter(or_(*filters)).all()


def _user_identity_keys(user: SeiUser) -> set[str]:
    return {key for key in (user.nome_key, user.nome_sei_key, user.usuario_sei_key) if key}


def _find_user_by_identity_key(db: Session, key: str) -> SeiUser | None:
    return (
        db.query(SeiUser)
        .filter(
            or_(
                SeiUser.nome_key == key,
                SeiUser.nome_sei_key == key,
                SeiUser.usuario_sei_key == key,
            )
        )
        .first()
    )


def _attach_alias_value(db: Session, target: SeiUser, value: object) -> tuple[SeiUserAlias | None, bool]:
    alias = clean_value(value)
    alias_key = normalize_identity(alias)
    if not alias or not alias_key or alias_key in _user_identity_keys(target):
        return None, False

    existing_alias = db.query(SeiUserAlias).filter(SeiUserAlias.alias_key == alias_key).first()
    if existing_alias:
        if existing_alias.sei_user_id != target.id:
            existing_alias.sei_user_id = target.id
        return existing_alias, False

    alias_row = SeiUserAlias(user=target, alias=alias, alias_key=alias_key)
    db.add(alias_row)
    return alias_row, True


def _merge_sei_user_into_target(db: Session, source: SeiUser, target: SeiUser) -> None:
    for token in (source.nome, source.nome_sei, source.usuario_sei):
        _attach_alias_value(db, target, token)

    for alias in list(source.aliases):
        if alias.alias_key in _user_identity_keys(target):
            db.delete(alias)
            continue

        duplicate = (
            db.query(SeiUserAlias)
            .filter(SeiUserAlias.alias_key == alias.alias_key, SeiUserAlias.id != alias.id)
            .first()
        )
        if duplicate:
            db.delete(alias)
        else:
            alias.sei_user_id = target.id

    db.delete(source)


def add_sei_user_alias(
    db: Session,
    sei_user_id: int,
    alias: object,
    *,
    merge_existing: bool = False,
) -> dict[str, object]:
    target = db.query(SeiUser).options(selectinload(SeiUser.aliases)).filter(SeiUser.id == sei_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario SEI nao encontrado.")

    cleaned_alias = clean_value(alias)
    alias_key = normalize_identity(cleaned_alias)
    if not cleaned_alias or not alias_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um nome historico valido.")

    merged_user: str | None = None

    existing_user = _find_user_by_identity_key(db, alias_key)
    if existing_user and existing_user.id != target.id:
        if not merge_existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"O nome informado ja pertence ao usuario SEI {existing_user.nome}. "
                    "Confirme a unificacao para prosseguir."
                ),
            )
        merged_user = existing_user.nome
        _merge_sei_user_into_target(db, existing_user, target)
        db.flush()

    existing_alias = db.query(SeiUserAlias).filter(SeiUserAlias.alias_key == alias_key).first()
    if existing_alias and existing_alias.sei_user_id != target.id:
        if not merge_existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este alias historico ja esta vinculado a outro usuario SEI.",
            )
        source_user = existing_alias.user
        merged_user = source_user.nome
        _merge_sei_user_into_target(db, source_user, target)
        db.flush()

    alias_row, created = _attach_alias_value(db, target, cleaned_alias)
    db.flush()

    return {
        "alias": cleaned_alias,
        "alias_id": alias_row.id if alias_row else None,
        "created": created,
        "merged_user": merged_user,
        "target_user": target.nome,
    }


def delete_sei_user_alias(db: Session, alias_id: int) -> str:
    alias = db.query(SeiUserAlias).filter(SeiUserAlias.id == alias_id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias historico nao encontrado.")

    value = alias.alias
    db.delete(alias)
    db.commit()
    return value


def list_attribution_candidates(db: Session) -> list[dict[str, object]]:
    lookup = build_sei_user_lookup(db)
    rows = (
        db.query(
            Processo.atribuicao,
            func.count(Processo.id),
            func.min(Processo.data_relatorio),
            func.max(Processo.data_relatorio),
        )
        .filter(Processo.atribuicao.is_not(None))
        .group_by(Processo.atribuicao)
        .order_by(Processo.atribuicao.asc())
        .all()
    )

    candidates: list[dict[str, object]] = []
    for atribuicao, total, primeira_data, ultima_data in rows:
        cleaned = clean_value(atribuicao)
        if not cleaned:
            continue
        candidates.append(
            {
                "atribuicao": cleaned,
                "total_processos": int(total or 0),
                "primeira_data": primeira_data,
                "ultima_data": ultima_data,
                "atribuicao_normalizada": resolve_atribuicao_canonica(cleaned, lookup),
            }
        )
    return candidates


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


def import_sei_users_rows(db: Session, rows: list[dict[str, object]]) -> dict[str, int]:
    imported = 0
    updated = 0
    total = 0

    for row in rows:
        if not clean_value(row.get("nome")):
            continue

        action, _ = upsert_sei_user(
            db,
            nome=row.get("nome"),
            nome_sei=row.get("nome_sei"),
            usuario_sei=row.get("usuario_sei"),
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

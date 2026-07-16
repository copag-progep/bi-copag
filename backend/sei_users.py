"""DE-PARA de servidores do SEI: normaliza nomes, resolve atribuições canônicas e sincroniza processos."""
from __future__ import annotations

import re
import unicodedata
from io import BytesIO

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session, selectinload

from .models import Processo, SeiUser, SeiUserAlias, SeiUserSetor


HEADER_ALIASES = {
    "nome": "nome",
    "nome_sei": "nome_sei",
    "nome sei": "nome_sei",
    "usuario_sei": "usuario_sei",
    "usuario sei": "usuario_sei",
    "usuário_sei": "usuario_sei",
    "usuário sei": "usuario_sei",
}

IGNORED_ATTRIBUTION_KEYS = {
    "sem atribuicao",
    "sem atribuicao definida",
    "nao atribuido",
    "nao atribuida",
    "nao informado",
    "nao informada",
    "sem responsavel",
    "sem servidor",
    "sem usuario",
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


def _find_user_by_identity_or_alias_key(db: Session, key: str) -> SeiUser | None:
    user = _find_user_by_identity_key(db, key)
    if user:
        return user

    alias = (
        db.query(SeiUserAlias)
        .options(selectinload(SeiUserAlias.user))
        .filter(SeiUserAlias.alias_key == key)
        .first()
    )
    return alias.user if alias else None


def _add_sei_user_setor_link(db: Session, sei_user: SeiUser, setor: str) -> bool:
    normalized_setor = (setor or "").upper().strip()
    if not normalized_setor:
        return False

    exists = (
        db.query(SeiUserSetor.id)
        .filter(SeiUserSetor.sei_user_id == sei_user.id, SeiUserSetor.setor == normalized_setor)
        .first()
    )
    if exists:
        return False

    db.add(SeiUserSetor(sei_user_id=sei_user.id, setor=normalized_setor))
    return True


def list_sei_user_names_for_setores(db: Session, setores: list[str] | tuple[str, ...]) -> list[str]:
    scoped_setores = sorted({setor.upper().strip() for setor in setores if setor and setor.strip()})
    if not scoped_setores:
        return []

    rows = (
        db.query(SeiUser.nome)
        .join(SeiUserSetor, SeiUser.id == SeiUserSetor.sei_user_id)
        .filter(SeiUserSetor.setor.in_(scoped_setores))
        .distinct()
        .order_by(SeiUser.nome.asc())
        .all()
    )
    return sorted({nome for (nome,) in rows if nome})


def _processo_atribuicao_scope(
    db: Session,
    *,
    setores: list[str] | None = None,
    data_relatorio=None,
    latest_only: bool = True,
) -> list[tuple[str, object]]:
    scoped_setores = sorted({setor.upper().strip() for setor in setores or [] if setor and setor.strip()})

    if data_relatorio is not None and scoped_setores:
        return [(setor, data_relatorio) for setor in scoped_setores]

    if data_relatorio is not None:
        query = (
            db.query(Processo.setor)
            .filter(Processo.data_relatorio == data_relatorio, Processo.atribuicao.is_not(None))
            .distinct()
        )
        if scoped_setores:
            query = query.filter(Processo.setor.in_(scoped_setores))
        return [(setor, data_relatorio) for (setor,) in query.all() if setor]

    if latest_only:
        query = (
            db.query(Processo.setor, func.max(Processo.data_relatorio))
            .filter(Processo.atribuicao.is_not(None))
        )
        if scoped_setores:
            query = query.filter(Processo.setor.in_(scoped_setores))
        return [(setor, latest_date) for setor, latest_date in query.group_by(Processo.setor).all() if setor and latest_date]

    query = db.query(Processo.setor, Processo.data_relatorio).filter(Processo.atribuicao.is_not(None)).distinct()
    if scoped_setores:
        query = query.filter(Processo.setor.in_(scoped_setores))
    return [(setor, report_date) for setor, report_date in query.all() if setor and report_date]


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


def discover_sei_users_from_processos(
    db: Session,
    *,
    setores: list[str] | None = None,
    data_relatorio=None,
    latest_only: bool = True,
) -> dict[str, object]:
    """Cria usuários SEI ausentes a partir das atribuições presentes nos processos.

    A descoberta usa, por padrão, o snapshot mais recente de cada setor para evitar
    trazer ruídos históricos para a base atual. Quando setor/data são informados
    pelo fluxo de upload, o escopo fica restrito ao snapshot recém-importado.
    """
    scope = _processo_atribuicao_scope(
        db,
        setores=setores,
        data_relatorio=data_relatorio,
        latest_only=latest_only,
    )
    if not scope:
        return {
            "created": 0,
            "links_added": 0,
            "matched_existing": 0,
            "ignored": 0,
            "total_candidates": 0,
            "users": [],
        }

    candidates: dict[str, dict[str, object]] = {}
    ignored = 0

    for setor, report_date in scope:
        rows = (
            db.query(Processo.atribuicao, func.count(Processo.id))
            .filter(
                Processo.setor == setor,
                Processo.data_relatorio == report_date,
                Processo.atribuicao.is_not(None),
            )
            .group_by(Processo.atribuicao)
            .all()
        )
        for raw_atribuicao, total in rows:
            cleaned = clean_value(raw_atribuicao)
            key = normalize_identity(cleaned)
            if not cleaned or not key or key in IGNORED_ATTRIBUTION_KEYS:
                ignored += 1
                continue

            entry = candidates.setdefault(
                key,
                {
                    "nome": cleaned,
                    "setores": set(),
                    "total_processos": 0,
                    "ultima_data": report_date,
                },
            )
            entry["setores"].add(str(setor).upper().strip())
            entry["total_processos"] = int(entry["total_processos"]) + int(total or 0)
            if report_date and (entry["ultima_data"] is None or report_date > entry["ultima_data"]):
                entry["ultima_data"] = report_date

    created_users: list[dict[str, object]] = []
    links_added = 0
    matched_existing = 0

    for key, entry in sorted(candidates.items(), key=lambda item: str(item[1]["nome"])):
        existing_user = _find_user_by_identity_or_alias_key(db, key)
        if existing_user:
            matched_existing += 1
            user = existing_user
            created = False
        else:
            _, user = upsert_sei_user(db, entry["nome"], entry["nome"], None)
            created = True

        user_links_added = 0
        for setor in sorted(entry["setores"]):
            if _add_sei_user_setor_link(db, user, setor):
                user_links_added += 1
                links_added += 1

        if created:
            created_users.append(
                {
                    "id": user.id,
                    "nome": user.nome,
                    "setores": sorted(entry["setores"]),
                    "total_processos": int(entry["total_processos"]),
                    "ultima_data": entry["ultima_data"],
                }
            )

    db.flush()
    return {
        "created": len(created_users),
        "links_added": links_added,
        "matched_existing": matched_existing,
        "ignored": ignored,
        "total_candidates": len(candidates),
        "users": created_users,
    }


def update_sei_user(db: Session, sei_user_id: int, nome: object, nome_sei: object, usuario_sei: object) -> SeiUser:
    user = db.query(SeiUser).options(selectinload(SeiUser.aliases)).filter(SeiUser.id == sei_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario SEI nao encontrado.")

    payload = apply_mapping_keys(nome, nome_sei, usuario_sei)
    keys = {key for key in (payload["nome_key"], payload["nome_sei_key"], payload["usuario_sei_key"]) if key}

    conflicting_user = (
        db.query(SeiUser)
        .filter(
            SeiUser.id != sei_user_id,
            or_(
                SeiUser.nome_key.in_(keys),
                SeiUser.nome_sei_key.in_(keys),
                SeiUser.usuario_sei_key.in_(keys),
            ),
        )
        .first()
        if keys
        else None
    )
    if conflicting_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Os dados informados ja pertencem ao usuario SEI {conflicting_user.nome}.",
        )

    conflicting_alias = (
        db.query(SeiUserAlias)
        .filter(SeiUserAlias.alias_key.in_(keys), SeiUserAlias.sei_user_id != sei_user_id)
        .first()
        if keys
        else None
    )
    if conflicting_alias:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Os dados informados ja estao vinculados como alias historico de {conflicting_alias.user.nome}.",
        )
    if keys:
        own_aliases = (
            db.query(SeiUserAlias)
            .filter(SeiUserAlias.alias_key.in_(keys), SeiUserAlias.sei_user_id == sei_user_id)
            .all()
        )
        for alias in own_aliases:
            db.delete(alias)

    user.nome = payload["nome"]
    user.nome_sei = payload["nome_sei"]
    user.usuario_sei = payload["usuario_sei"]
    user.nome_key = payload["nome_key"]
    user.nome_sei_key = payload["nome_sei_key"]
    user.usuario_sei_key = payload["usuario_sei_key"]
    db.flush()
    return user


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

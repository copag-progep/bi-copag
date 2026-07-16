"""Testes da descoberta automatica de usuarios SEI a partir dos processos.

Usa SQLite in-memory isolado (nao toca no banco real).
Executar: python backend/tests/test_sei_users_discovery.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database import Base  # noqa: E402
from backend import models  # noqa: E402  (registra as tabelas)
from backend.models import Processo, SeiUser, SeiUserAlias, SeiUserSetor, Upload  # noqa: E402
from backend.sei_users import discover_sei_users_from_processos, normalize_identity, upsert_sei_user  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

HOJE = date.today()


def _processo(db, protocolo, setor, atribuicao, data_rel):
    upload = Upload(
        setor=setor,
        data_relatorio=data_rel,
        original_filename=f"{setor}-{data_rel}.csv",
        file_hash=f"{protocolo}-{setor}-{data_rel}",
        total_records=1,
    )
    db.add(upload)
    db.flush()
    db.add(
        Processo(
            protocolo=protocolo,
            setor=setor,
            atribuicao=atribuicao,
            atribuicao_normalizada=atribuicao,
            data_relatorio=data_rel,
            upload_id=upload.id,
        )
    )
    db.flush()


def test_descoberta_cria_usuario_e_vinculo_setor():
    db = _Session()
    try:
        _processo(db, "P1", "DIAPE", "Elber Fernandes Albuquerque", HOJE)
        result = discover_sei_users_from_processos(db, setores=["DIAPE"], data_relatorio=HOJE)

        user = db.query(SeiUser).filter(SeiUser.nome == "Elber Fernandes Albuquerque").one()
        setores = [row.setor for row in db.query(SeiUserSetor).filter(SeiUserSetor.sei_user_id == user.id).all()]

        assert result["created"] == 1
        assert result["links_added"] == 1
        assert setores == ["DIAPE"]
    finally:
        db.rollback()
        db.close()


def test_descoberta_nao_duplica_alias_existente_e_vincula_setor():
    db = _Session()
    try:
        _, principal = upsert_sei_user(db, "Servidor Principal", None, None)
        db.add(
            SeiUserAlias(
                sei_user_id=principal.id,
                alias="Nome Novo No SEI",
                alias_key=normalize_identity("Nome Novo No SEI"),
            )
        )
        db.flush()
        _processo(db, "P2", "DICAF", "Nome Novo No SEI", HOJE)

        result = discover_sei_users_from_processos(db, setores=["DICAF"], data_relatorio=HOJE)
        users = db.query(SeiUser).all()
        setores = [row.setor for row in db.query(SeiUserSetor).filter(SeiUserSetor.sei_user_id == principal.id).all()]

        assert result["created"] == 0
        assert result["matched_existing"] == 1
        assert result["links_added"] == 1
        assert len(users) == 1
        assert setores == ["DICAF"]
    finally:
        db.rollback()
        db.close()


def test_descoberta_ignora_marcadores_sem_atribuicao():
    db = _Session()
    try:
        _processo(db, "P3", "DIAPE", "Sem atribuição", HOJE)
        result = discover_sei_users_from_processos(db, setores=["DIAPE"], data_relatorio=HOJE)

        assert result["created"] == 0
        assert result["ignored"] == 1
        assert db.query(SeiUser).count() == 0
    finally:
        db.rollback()
        db.close()


def test_descoberta_manual_usa_apenas_snapshot_mais_recente_por_setor():
    db = _Session()
    try:
        _processo(db, "OLD", "DIAPE", "Servidor Antigo", HOJE - timedelta(days=7))
        _processo(db, "NEW", "DIAPE", "Servidor Atual", HOJE)

        result = discover_sei_users_from_processos(db)
        nomes = {row.nome for row in db.query(SeiUser).all()}

        assert result["created"] == 1
        assert nomes == {"Servidor Atual"}
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"✓ {test.__name__}")
    print(f"\n{len(tests)} testes de descoberta de usuarios SEI passaram.")

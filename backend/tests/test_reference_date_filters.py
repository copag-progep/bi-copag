"""Regressão: filtros de atribuição/tipo não podem mover a data de referência.

Executar: python backend/tests/test_reference_date_filters.py
"""
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database import Base  # noqa: E402
from backend import models  # noqa: E402  (registra as tabelas)
from backend.analytics import (  # noqa: E402
    AnalyticsFilters,
    _resolve_reference_date,
    clear_analytics_cache,
    get_attributions_data,
    get_server_profile,
)
from backend.models import Processo, Upload  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

JUNHO = date(2026, 6, 17)
JULHO = date(2026, 7, 15)
MELISSA = "MELISSA MELOSSELLI MATOS PEREIRA"
DENILSON = "DENILSON SALES DO NASCIMENTO"


def _snapshot(db, *, protocolo, setor, atribuicao, data_relatorio):
    upload = Upload(
        setor=setor,
        data_relatorio=data_relatorio,
        original_filename=f"{setor}-{data_relatorio}.csv",
        file_hash=f"{protocolo}-{setor}-{data_relatorio}",
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
            tipo="Pessoal: Aposentadoria por Tempo de Serviço",
            data_relatorio=data_relatorio,
            upload_id=upload.id,
        )
    )
    db.flush()


def _seed_melissa_para_denilson(db):
    _snapshot(
        db,
        protocolo="23067.003793/2018-87",
        setor="DIAPE",
        atribuicao=MELISSA,
        data_relatorio=JUNHO,
    )
    _snapshot(
        db,
        protocolo="23067.003793/2018-87",
        setor="DIAPE",
        atribuicao=DENILSON,
        data_relatorio=JULHO,
    )


def test_atribuicao_nao_desloca_data_referencia_para_ultimo_historico():
    db = _Session()
    clear_analytics_cache()
    try:
        _seed_melissa_para_denilson(db)
        filters = AnalyticsFilters(data_referencia=JULHO, setor="DIAPE", atribuicao=MELISSA)

        assert _resolve_reference_date(db, filters) == JULHO
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


def test_attributions_nao_lista_processo_que_saiu_da_atribuicao_na_referencia():
    db = _Session()
    clear_analytics_cache()
    try:
        _seed_melissa_para_denilson(db)

        melissa = get_attributions_data(
            db,
            AnalyticsFilters(data_referencia=JULHO, setor="DIAPE", atribuicao=MELISSA),
        )
        denilson = get_attributions_data(
            db,
            AnalyticsFilters(data_referencia=JULHO, setor="DIAPE", atribuicao=DENILSON),
        )

        assert melissa["data_referencia"] == "2026-07-15"
        assert melissa["total"] == 0
        assert melissa["items"] == []
        assert denilson["data_referencia"] == "2026-07-15"
        assert denilson["total"] == 1
        assert denilson["items"][0]["protocolo"] == "23067.003793/2018-87"
        assert denilson["items"][0]["atribuicao"] == DENILSON
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


def test_server_profile_usa_referencia_atual_mesmo_sem_carga_na_atribuicao():
    db = _Session()
    clear_analytics_cache()
    try:
        _seed_melissa_para_denilson(db)
        profile = get_server_profile(
            db,
            AnalyticsFilters(data_referencia=JULHO, atribuicao=MELISSA),
        )

        assert profile["encontrado"] is True
        assert profile["data_referencia"] == "2026-07-15"
        assert profile["carga_atual"] == 0
        assert profile["total_finalizados"] == 1
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"✓ {test.__name__}")
    print(f"\n{len(tests)} testes de referência temporal passaram.")

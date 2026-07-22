"""Regressão: filtros de atribuição/tipo não podem mover a data de referência.

Executar: python backend/tests/test_reference_date_filters.py
"""
import json
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
    get_risk_scores,
    get_stale_processes_data,
    get_server_profile,
)
from backend.models import Processo, Upload, User  # noqa: E402
from backend.main import attributions_list  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

JUNHO = date(2026, 6, 17)
JULHO = date(2026, 7, 15)
MELISSA = "MELISSA MELOSSELLI MATOS PEREIRA"
DENILSON = "DENILSON SALES DO NASCIMENTO"
NAIARA = "NAIARA JADY CANDIDO OLIVEIRA"


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


def _seed_sem_atribuicao_para_naiara(db):
    for snapshot_day, assignment in [
        (date(2026, 4, 26), None),
        (date(2026, 7, 16), None),
        (date(2026, 7, 17), NAIARA),
        (date(2026, 7, 21), NAIARA),
    ]:
        _snapshot(
            db,
            protocolo="23067.055309/2025-24",
            setor="DIAPE",
            atribuicao=assignment,
            data_relatorio=snapshot_day,
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


def test_tempo_no_setor_nao_reinicia_quando_atribuicao_muda():
    db = _Session()
    clear_analytics_cache()
    try:
        _seed_sem_atribuicao_para_naiara(db)
        filters = AnalyticsFilters(
            data_referencia=date(2026, 7, 21), setor="DIAPE", atribuicao=NAIARA,
        )

        attributions = get_attributions_data(db, filters)
        assert attributions["total"] == 1
        item = attributions["items"][0]
        assert item["entrada_setor"] == "2026-04-26"
        assert item["dias_no_setor"] == 86
        assert item["entrada_atribuicao"] == "2026-07-17"
        assert item["dias_com_atribuicao"] == 4

        stale = get_stale_processes_data(db, filters)
        assert stale["processos"][0]["entrada_setor"] == "2026-04-26"
        assert stale["processos"][0]["dias_sem_movimentacao"] == 86

        risk = get_risk_scores(db, filters)
        assert risk["processos"][0]["dias_no_setor"] == 86
        assert risk["processos"][0]["entrada_setor"] == "2026-04-26"
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


def test_faixa_da_api_pode_usar_dias_setor_ou_dias_atribuicao():
    db = _Session()
    clear_analytics_cache()
    try:
        _seed_sem_atribuicao_para_naiara(db)
        admin = User(name="Admin", email="admin-faixas@teste.local", password_hash="x", is_admin=True)
        common = dict(
            data_referencia=date(2026, 7, 21), setor="DIAPE", tipo=None, atribuicao=NAIARA,
            min_dias=80, max_dias=None, sem_atribuicao=False, sort_by="dias_setor",
            sort_dir="desc", protocolo_busca=None, page=1, page_size=50,
            current_user=admin, db=db,
        )
        by_sector = json.loads(attributions_list(dias_base="setor", **common).body)
        by_assignment = json.loads(attributions_list(dias_base="atribuicao", **common).body)
        assert by_sector["total"] == 1
        assert by_assignment["total"] == 0
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

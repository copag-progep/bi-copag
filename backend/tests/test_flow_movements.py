"""Regressões da classificação detalhada de entradas e saídas."""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.analytics import (  # noqa: E402
    AnalyticsFilters,
    clear_analytics_cache,
    get_entries_exits_data,
    get_flow_details_data,
)
from backend.database import Base  # noqa: E402
from backend.models import Processo, Upload  # noqa: E402
from backend.models import User  # noqa: E402
from backend.main import flow_details  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

ANTERIOR = date(2026, 7, 17)
ATUAL = date(2026, 7, 20)


def _processo(db, protocolo, setor, dia, atribuicao, *, normalizada=None, tipo="Tipo A"):
    upload = Upload(
        setor=setor,
        data_relatorio=dia,
        original_filename=f"{setor}-{dia}-{protocolo}.csv",
        file_hash=f"{setor}-{dia}-{protocolo}",
        total_records=1,
    )
    db.add(upload)
    db.flush()
    db.add(Processo(
        protocolo=protocolo,
        setor=setor,
        atribuicao=atribuicao,
        atribuicao_normalizada=normalizada if normalizada is not None else atribuicao,
        tipo=tipo,
        data_relatorio=dia,
        upload_id=upload.id,
    ))
    db.flush()


def _run(seed, filters=None):
    db = _Session()
    clear_analytics_cache()
    try:
        seed(db)
        return get_flow_details_data(db, filters or AnalyticsFilters(data_referencia=ATUAL))
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


def test_detalhe_e_resumo_usam_as_mesmas_movimentacoes():
    def seed(db):
        _processo(db, "FICA", "DIAPE", ANTERIOR, "ANA")
        _processo(db, "FICA", "DIAPE", ATUAL, "ANA")
        _processo(db, "SAIU", "DIAPE", ANTERIOR, "BIA")
        _processo(db, "ENTROU", "DIAPE", ATUAL, "CARLA")

    result = _run(seed)
    assert {(item["protocolo"], item["fluxo"]) for item in result["movimentacoes"]} == {
        ("ENTROU", "entrada"),
        ("SAIU", "saida"),
    }
    assert result["resumo_setorial"] == [{
        "setor": "DIAPE", "entradas": 1, "saidas": 1, "saldo": 0, "carga_atual": 2,
    }]


def test_troca_de_atribuicao_no_mesmo_setor_nao_cria_fluxo_falso():
    def seed(db):
        _processo(db, "P1", "DIAPE", ANTERIOR, "MELISSA")
        _processo(db, "P1", "DIAPE", ATUAL, "DENILSON")

    antigo = _run(seed, AnalyticsFilters(data_referencia=ATUAL, atribuicao="MELISSA"))
    novo = _run(seed, AnalyticsFilters(data_referencia=ATUAL, atribuicao="DENILSON"))
    assert antigo["movimentacoes"] == []
    assert novo["movimentacoes"] == []


def test_saida_usa_atribuicao_normalizada_do_snapshot_anterior():
    def seed(db):
        _processo(db, "P2", "DIAPE", ANTERIOR, "maria.sei", normalizada="MARIA DA SILVA")
        _processo(db, "BASE", "DIAPE", ATUAL, "OUTRA")

    result = _run(seed)
    saida = next(item for item in result["movimentacoes"] if item["protocolo"] == "P2")
    assert saida["fluxo"] == "saida"
    assert saida["atribuicao"] == "MARIA DA SILVA"


def test_transferencia_entre_setores_gera_saida_e_entrada():
    def seed(db):
        _processo(db, "P3", "DIAPE", ANTERIOR, "ANA")
        _processo(db, "P3", "DICAF", ATUAL, "BIA")

    result = _run(seed)
    assert {(item["setor"], item["fluxo"]) for item in result["movimentacoes"]} == {
        ("DIAPE", "saida"),
        ("DICAF", "entrada"),
    }


def test_sem_snapshot_anterior_retorna_comparacao_indisponivel():
    def seed(db):
        _processo(db, "P4", "DIAPE", ATUAL, "ANA")

    result = _run(seed)
    assert result["comparacao_disponivel"] is False
    assert result["data_anterior"] is None
    assert result["movimentacoes"] == []
    assert result["resumo_setorial"][0]["entradas"] == 0


def test_escopo_setorial_limita_detalhes_e_resumo():
    def seed(db):
        _processo(db, "D1", "DIAPE", ANTERIOR, "ANA")
        _processo(db, "D2", "DICAF", ANTERIOR, "BIA")
        _processo(db, "BASE", "DIAPE", ATUAL, "ANA")
        _processo(db, "BASE2", "DICAF", ATUAL, "BIA")

    result = _run(seed, AnalyticsFilters(data_referencia=ATUAL, setores_permitidos=("DIAPE",)))
    assert {item["setor"] for item in result["movimentacoes"]} == {"DIAPE"}
    assert {item["setor"] for item in result["resumo_setorial"]} == {"DIAPE"}


def test_fluxo_agregado_repete_totais_do_detalhe():
    db = _Session()
    clear_analytics_cache()
    try:
        _processo(db, "S1", "DIAPE", ANTERIOR, "ANA")
        _processo(db, "E1", "DIAPE", ATUAL, "BIA")
        filters = AnalyticsFilters(data_referencia=ATUAL)
        detail = get_flow_details_data(db, filters)
        aggregate = get_entries_exits_data(db, filters)
        assert aggregate["resumo_setorial"] == detail["resumo_setorial"]
        assert aggregate["comparacao_disponivel"] == detail["comparacao_disponivel"]
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()


def test_endpoint_ordena_e_pagina_movimentacoes():
    db = _Session()
    clear_analytics_cache()
    try:
        _processo(db, "BASE", "DIAPE", ANTERIOR, "ANA")
        _processo(db, "100", "DIAPE", ATUAL, "ANA")
        _processo(db, "200", "DIAPE", ATUAL, "BIA")
        admin = User(name="Admin", email="admin@local", password_hash="x", is_admin=True)
        response = flow_details(
            data_referencia=ATUAL,
            data_inicial=None,
            data_final=None,
            setor=None,
            tipo=None,
            atribuicao=None,
            fluxo="entrada",
            protocolo_busca=None,
            sort_by="protocolo",
            sort_dir="desc",
            page=1,
            page_size=1,
            current_user=admin,
            db=db,
        )
        payload = json.loads(response.body)
        assert payload["total"] == 2
        assert payload["total_pages"] == 2
        assert payload["items"][0]["protocolo"] == "200"
        assert payload["total_entradas"] == 2
        assert payload["total_saidas"] == 1
    finally:
        db.rollback()
        db.close()
        clear_analytics_cache()

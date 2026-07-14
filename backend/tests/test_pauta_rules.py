"""Testes das regras da Pauta Prioritária: situação derivada, duplicidade
global e fallback da atribuição atual.

Usa SQLite in-memory isolado (não toca no banco real).
Executar: python backend/tests/test_pauta_rules.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Banco de teste isolado antes de importar qualquer módulo do app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from backend.database import Base  # noqa: E402
from backend import models  # noqa: E402  (registra as tabelas)
from backend.models import PautaSessao, PautaItem, Processo, Upload  # noqa: E402
from backend.main import (  # noqa: E402
    _situacao_pauta_sessao,
    _pauta_item_em_sessao_ativa,
    _atribuicao_atual_por_processo,
)

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

HOJE = date.today()


def _sessao(db, ativa=True, inicio=None, fim=None):
    s = PautaSessao(
        titulo="Sessão teste",
        data_inicio=inicio or HOJE,
        data_fim=fim,
        ativa=ativa,
    )
    db.add(s)
    db.flush()
    return s


def _item(db, sessao, protocolo="P1", setor="DIAPE", entrada=None, status="pendente"):
    it = PautaItem(
        sessao_id=sessao.id, protocolo=protocolo, setor=setor,
        entrada_setor=entrada, status=status,
    )
    db.add(it)
    db.flush()
    return it


def _processo(db, protocolo, setor, atribuicao, atribuicao_normalizada, data_rel):
    up = Upload(setor=setor, data_relatorio=data_rel, original_filename="t.csv", file_hash=f"{protocolo}-{data_rel}", total_records=1)
    db.add(up)
    db.flush()
    db.add(Processo(
        protocolo=protocolo, setor=setor,
        atribuicao=atribuicao, atribuicao_normalizada=atribuicao_normalizada,
        data_relatorio=data_rel, upload_id=up.id,
    ))
    db.flush()


# ── Situação derivada ─────────────────────────────────────────────────────

def test_situacao_a_iniciar():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE + timedelta(days=2))
        assert _situacao_pauta_sessao(s) == "a_iniciar"
    finally:
        db.rollback(); db.close()


def test_situacao_em_andamento_sem_prazo():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=1), fim=None)
        assert _situacao_pauta_sessao(s) == "em_andamento"
    finally:
        db.rollback(); db.close()


def test_situacao_prazo_hoje_ainda_em_andamento():
    """data_fim == hoje: ainda EM ANDAMENTO (encerra só amanhã)."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=3), fim=HOJE)
        assert _situacao_pauta_sessao(s) == "em_andamento"
    finally:
        db.rollback(); db.close()


def test_situacao_encerrada_por_prazo():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=5), fim=HOJE - timedelta(days=1))
        assert _situacao_pauta_sessao(s) == "encerrada"
    finally:
        db.rollback(); db.close()


def test_situacao_encerrada_por_ativa_false():
    db = _Session()
    try:
        s = _sessao(db, ativa=False, inicio=HOJE, fim=HOJE + timedelta(days=5))
        assert _situacao_pauta_sessao(s) == "encerrada"
    finally:
        db.rollback(); db.close()


# ── Duplicidade global ────────────────────────────────────────────────────

def test_duplicidade_detecta_em_sessao_ativa():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        _item(db, s, protocolo="X1", setor="DIAPE", entrada=HOJE)
        achado = _pauta_item_em_sessao_ativa(db, "X1", "DIAPE", HOJE)
        assert achado is not None
    finally:
        db.rollback(); db.close()


def test_duplicidade_ignora_sessao_encerrada():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=9), fim=HOJE - timedelta(days=2))
        _item(db, s, protocolo="X2", setor="DIAPE", entrada=HOJE)
        assert _pauta_item_em_sessao_ativa(db, "X2", "DIAPE", HOJE) is None
    finally:
        db.rollback(); db.close()


def test_duplicidade_ignora_arquivado():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        _item(db, s, protocolo="X3", setor="DIAPE", entrada=HOJE, status="arquivado")
        assert _pauta_item_em_sessao_ativa(db, "X3", "DIAPE", HOJE) is None
    finally:
        db.rollback(); db.close()


def test_duplicidade_entrada_diferente_e_permitida():
    """Mesmo processo/setor, período diferente → NÃO é duplicata."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        _item(db, s, protocolo="X4", setor="DIAPE", entrada=HOJE - timedelta(days=30))
        # entrada_setor diferente → livre para incluir
        assert _pauta_item_em_sessao_ativa(db, "X4", "DIAPE", HOJE) is None
    finally:
        db.rollback(); db.close()


# ── Fallback da atribuição atual ──────────────────────────────────────────

def test_atribuicao_atual_presente_sem_normalizacao():
    """Processo no snapshot atual sem atribuicao_normalizada → usa texto bruto,
    e a CHAVE existe no dict (presente, não histórico)."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        item = _item(db, s, protocolo="A1", setor="DIAPE", entrada=HOJE)
        _processo(db, "A1", "DIAPE", "Fulano Bruto", None, HOJE)
        mapa = _atribuicao_atual_por_processo(db, [item])
        assert ("A1", "DIAPE") in mapa            # presente
        assert mapa[("A1", "DIAPE")] == "Fulano Bruto"
    finally:
        db.rollback(); db.close()


def test_atribuicao_ausente_do_snapshot_nao_entra_no_mapa():
    """Processo que saiu do setor → chave ausente → chamador usa fallback histórico."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        item = _item(db, s, protocolo="A2", setor="DIAPE", entrada=HOJE)
        # snapshot mais recente do setor NÃO contém A2
        _processo(db, "OUTRO", "DIAPE", "Beltrano", "Beltrano", HOJE)
        mapa = _atribuicao_atual_por_processo(db, [item])
        assert ("A2", "DIAPE") not in mapa
    finally:
        db.rollback(); db.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"✓ {t.__name__}")
    print(f"\n{len(tests)} testes de regras da pauta passaram.")

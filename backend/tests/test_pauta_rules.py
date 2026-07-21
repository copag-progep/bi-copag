"""Testes das regras da Pauta Prioritária: situação derivada, duplicidade
global e fallback da atribuição atual.

Usa SQLite in-memory isolado (não toca no banco real).
Executar: python backend/tests/test_pauta_rules.py
"""
import os
import sys
from datetime import date, timedelta
from itertools import count
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Banco de teste isolado antes de importar qualquer módulo do app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from backend.database import Base  # noqa: E402
from backend import models  # noqa: E402  (registra as tabelas)
from backend.models import AuditLog, PautaSessao, PautaItem, Processo, Upload, User  # noqa: E402
from backend.main import (  # noqa: E402
    _situacao_pauta_sessao,
    _pauta_item_em_sessao_ativa,
    _atribuicao_atual_por_processo,
    CopyPendingPayload,
    copy_pending_to_new_session,
    PautaItemCreate,
    PautaItemUpdate,
    add_pauta_item,
    update_pauta_item,
)

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)

HOJE = date.today()
_USER_SEQUENCE = count(1)


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


def _admin(db):
    sequence = next(_USER_SEQUENCE)
    user = User(
        name="Admin Teste",
        email=f"admin-{sequence}@teste.local",
        password_hash="x",
        is_admin=True,
    )
    db.add(user)
    db.flush()
    return user


def _user(db, name="Responsável Teste"):
    sequence = next(_USER_SEQUENCE)
    user = User(
        name=name,
        email=f"{name}-{sequence}@teste.local".replace(" ", "").lower(),
        password_hash="x",
        is_admin=False,
    )
    db.add(user)
    db.flush()
    return user


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
        chave = ("A1", "DIAPE", HOJE)
        assert chave in mapa                       # presente na passagem corrente
        assert mapa[chave] == "Fulano Bruto"
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
        assert ("A2", "DIAPE", HOJE) not in mapa
    finally:
        db.rollback(); db.close()


def test_atribuicao_reingresso_nao_contamina_item_historico():
    """Processo saiu e voltou ao mesmo setor com nova entrada_setor: o item
    histórico (entrada antiga) NÃO recebe a atribuição da nova passagem."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        entrada_antiga = HOJE - timedelta(days=40)
        item_hist = _item(db, s, protocolo="R1", setor="DIAPE", entrada=entrada_antiga)
        # R1 esteve no setor na entrada antiga, sumiu no snapshot intermediário,
        # e voltou no snapshot atual. A passagem corrente começou hoje, não na
        # entrada antiga do item histórico.
        _processo(db, "R1", "DIAPE", "Passagem Antiga", "Passagem Antiga", entrada_antiga)
        _processo(db, "OUTRO", "DIAPE", "Beltrano", "Beltrano", HOJE - timedelta(days=20))
        _processo(db, "R1", "DIAPE", "Nova Passagem", "Nova Passagem", HOJE)
        mapa = _atribuicao_atual_por_processo(db, [item_hist])
        # A chave do item histórico não deve estar presente → cai no fallback
        assert ("R1", "DIAPE", entrada_antiga) not in mapa
    finally:
        db.rollback(); db.close()


def test_atribuicao_passagem_continua_usa_atual():
    """Presença contínua até o snapshot atual → usa a atribuição mais recente."""
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        entrada = HOJE - timedelta(days=2)
        item = _item(db, s, protocolo="C1", setor="DIAPE", entrada=entrada)
        _processo(db, "C1", "DIAPE", "Antiga", "Antiga", entrada)
        _processo(db, "C1", "DIAPE", "Meio", "Meio", HOJE - timedelta(days=1))
        _processo(db, "C1", "DIAPE", "Atual", "Atual", HOJE)
        mapa = _atribuicao_atual_por_processo(db, [item])
        assert mapa[("C1", "DIAPE", entrada)] == "Atual"
    finally:
        db.rollback(); db.close()


# ── Prazo do item (inclusão e edição admin-only) ────────────────────────────

def test_prazo_pode_ser_definido_na_inclusao_do_item():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        admin = _admin(db)
        novo_prazo = HOJE + timedelta(days=3)
        result = add_pauta_item(
            s.id,
            PautaItemCreate(protocolo="PZ1", setor="DIAPE", entrada_setor=HOJE, prazo=novo_prazo),
            current_admin=admin,
            db=db,
        )
        item = db.query(PautaItem).filter(PautaItem.id == result["id"]).first()
        assert item is not None
        assert item.prazo == novo_prazo
    finally:
        db.rollback(); db.close()


def test_prazo_pode_ser_limpo_com_null_explicito():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        admin = _admin(db)
        item = _item(db, s, protocolo="PZ2", setor="DIAPE", entrada=HOJE)
        item.prazo = HOJE + timedelta(days=5)
        db.flush()
        # exclude_unset garante que "prazo": None limpa o campo (não é ignorado como exclude_none faria)
        update_pauta_item(item.id, PautaItemUpdate(prazo=None), current_user=admin, db=db)
        db.refresh(item)
        assert item.prazo is None
    finally:
        db.rollback(); db.close()


def test_prazo_nao_pode_ser_editado_pelo_responsavel_atribuido():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        responsavel = _user(db, "Sicrano")
        item = _item(db, s, protocolo="PZ3", setor="DIAPE", entrada=HOJE)
        item.assigned_to = responsavel.id
        db.flush()
        try:
            update_pauta_item(item.id, PautaItemUpdate(prazo=HOJE + timedelta(days=1)), current_user=responsavel, db=db)
            assert False, "responsável atribuído não deveria poder editar prazo"
        except HTTPException as exc:
            assert exc.status_code == 403
    finally:
        db.rollback(); db.close()


def test_update_item_rejeita_campo_legacy_nota_responsavel():
    try:
        PautaItemUpdate(nota_responsavel="texto antigo")
        assert False, "campo legacy nota_responsavel deveria ser rejeitado"
    except ValidationError:
        pass


# ── Copy pending ─────────────────────────────────────────────────────────────

def test_copy_pending_rejeita_prazo_anterior_ao_inicio():
    db = _Session()
    try:
        s = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=5))
        _item(db, s, protocolo="CP1", setor="DIAPE", entrada=HOJE)
        admin = _admin(db)
        payload = CopyPendingPayload(
            titulo="Nova sessão",
            data_inicio=HOJE,
            data_fim=HOJE - timedelta(days=1),
        )
        try:
            copy_pending_to_new_session(s.id, payload, current_admin=admin, db=db)
            assert False, "copy_pending deveria rejeitar prazo anterior ao início"
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "prazo" in exc.detail.lower()
    finally:
        db.rollback(); db.close()


def test_copy_pending_encerra_origem_e_cria_nova_sessao():
    db = _Session()
    try:
        source = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=7), fim=HOJE)
        item_origem = _item(db, source, protocolo="CP2", setor="DIAPE", entrada=HOJE - timedelta(days=7))
        item_origem.prazo = HOJE + timedelta(days=10)
        db.flush()
        admin = _admin(db)
        payload = CopyPendingPayload(
            titulo="Nova sessão com pendências",
            data_inicio=HOJE + timedelta(days=1),
            data_fim=HOJE + timedelta(days=7),
        )
        result = copy_pending_to_new_session(source.id, payload, current_admin=admin, db=db)

        db.refresh(source)
        nova = db.query(PautaSessao).filter(PautaSessao.id == result["nova_sessao_id"]).first()
        assert source.ativa is False
        assert nova is not None
        assert result["itens_copiados"] == 1
        item_copiado = db.query(PautaItem).filter(PautaItem.sessao_id == nova.id, PautaItem.protocolo == "CP2").first()
        assert item_copiado is not None
        assert item_copiado.prazo == item_origem.prazo  # prazo é preservado ao copiar pendências
    finally:
        db.query(AuditLog).delete()
        db.query(PautaItem).delete()
        db.query(PautaSessao).delete()
        db.query(User).delete()
        db.commit()
        db.close()


def test_copy_pending_para_sessao_existente():
    db = _Session()
    try:
        source = _sessao(db, ativa=True, inicio=HOJE - timedelta(days=7), fim=HOJE)
        target = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=7))
        target.titulo = "Sessão destino existente"
        item_origem = _item(db, source, protocolo="CP3", setor="DIAPE", entrada=HOJE - timedelta(days=7))
        item_origem.prazo = HOJE + timedelta(days=3)
        admin = _admin(db)

        result = copy_pending_to_new_session(
            source.id,
            CopyPendingPayload(destination_mode="existing", destination_session_id=target.id),
            current_admin=admin,
            db=db,
        )

        db.refresh(source)
        db.refresh(target)
        copied = db.query(PautaItem).filter(PautaItem.sessao_id == target.id, PautaItem.protocolo == "CP3").first()
        assert source.ativa is False
        assert target.ativa is True
        assert result["sessao_destino_id"] == target.id
        assert result["destino_tipo"] == "existing"
        assert result["itens_copiados"] == 1
        assert copied is not None
        assert copied.prazo == item_origem.prazo
    finally:
        db.query(AuditLog).delete()
        db.query(PautaItem).delete()
        db.query(PautaSessao).delete()
        db.query(User).delete()
        db.commit()
        db.close()


def test_copy_pending_rejeita_destino_encerrado_sem_encerrar_origem():
    db = _Session()
    try:
        source = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=2))
        target = _sessao(db, ativa=False, inicio=HOJE - timedelta(days=7), fim=HOJE - timedelta(days=1))
        _item(db, source, protocolo="CP4", setor="DIAPE", entrada=HOJE)
        admin = _admin(db)
        try:
            copy_pending_to_new_session(
                source.id,
                CopyPendingPayload(destination_mode="existing", destination_session_id=target.id),
                current_admin=admin,
                db=db,
            )
            assert False, "destino encerrado deveria ser rejeitado"
        except HTTPException as exc:
            assert exc.status_code == 409
        db.refresh(source)
        assert source.ativa is True
    finally:
        db.rollback(); db.close()


def test_copy_pending_conflito_total_preserva_origem():
    db = _Session()
    try:
        source = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=2))
        target = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=7))
        entrada = HOJE - timedelta(days=3)
        _item(db, source, protocolo="CP5", setor="DIAPE", entrada=entrada)
        _item(db, target, protocolo="CP5", setor="DIAPE", entrada=entrada)
        admin = _admin(db)
        try:
            copy_pending_to_new_session(
                source.id,
                CopyPendingPayload(destination_mode="existing", destination_session_id=target.id),
                current_admin=admin,
                db=db,
            )
            assert False, "conflito total deveria impedir a cópia"
        except HTTPException as exc:
            assert exc.status_code == 409
        db.refresh(source)
        assert source.ativa is True
        assert db.query(PautaItem).filter(PautaItem.sessao_id == target.id).count() == 1
    finally:
        db.rollback(); db.close()


def test_copy_pending_conflito_parcial_copia_apenas_transferiveis():
    db = _Session()
    try:
        source = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=2))
        target = _sessao(db, ativa=True, inicio=HOJE, fim=HOJE + timedelta(days=7))
        entrada = HOJE - timedelta(days=3)
        _item(db, source, protocolo="CP6-A", setor="DIAPE", entrada=entrada)
        _item(db, source, protocolo="CP6-B", setor="DIAPE", entrada=entrada)
        _item(db, target, protocolo="CP6-A", setor="DIAPE", entrada=entrada)
        admin = _admin(db)

        result = copy_pending_to_new_session(
            source.id,
            CopyPendingPayload(destination_mode="existing", destination_session_id=target.id),
            current_admin=admin,
            db=db,
        )

        assert result["itens_copiados"] == 1
        assert result["ignorados"] == 1
        assert result["conflitos"][0]["motivo"] == "ja_existe_no_destino"
        assert db.query(PautaItem).filter(PautaItem.sessao_id == target.id).count() == 2
    finally:
        db.query(AuditLog).delete()
        db.query(PautaItem).delete()
        db.query(PautaSessao).delete()
        db.query(User).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"✓ {t.__name__}")
    print(f"\n{len(tests)} testes de regras da pauta passaram.")

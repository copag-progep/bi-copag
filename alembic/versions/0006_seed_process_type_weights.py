"""popular pesos iniciais por tipo de processo

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-25 00:00:00.000000

Insere pesos iniciais para o Score de Risco conforme priorização
gerencial da COPAG. Tipos não listados permanecem neutros, com peso
implícito 1.00.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALTA_PRIORIDADE = [
    "Pessoal: Pensão por Morte de Servidor",
    "Pessoal: Aposentadoria por Tempo de Serviço (Integral/Proporcional)",
    "Pessoal: Aposentadoria por Incapacidade",
    "Pessoal: Aposentadoria Compulsória",
    "Pessoal: Falecimento de Servidor",
    "Pessoal: Atendimento à Diligência CGU - Pensão Civil por Morte",
    "Pessoal: Atendimento à Diligência CGU - Aposentadoria",
    "Pessoal: Pensão Alimentícia Judicial",
    "Administração Geral: Ação Judicial",
    "Acesso à Informação: Demanda Externa",
    "Acesso à Informação: Demanda do e-SIC",
]

PRIORIDADE_MEDIA = [
    "Auditoria: Demanda Externa CGU",
    "Auditoria: Demanda Externa TCU",
    "Auditoria: Demanda Interna - Ação de Auditoria",
    "Pessoal: Reposição ao Erário",
    "Pessoal: Saúde - Ressarcimento ao Erário",
    "Orçamento e Finanças: Cobranças de Valores a Receber (Inclusive Dívida Ativa)",
]

PESO_REDUZIDO = [
    "Gestão da Informação: Empréstimo de Documentos e Processos",
    "Gestão da Informação: Desarquivamento de Documentos e Processos",
    "Pessoal: RAIS, DIRF, GFIP e Outros",
    "Administração Geral: Reuniões de Colegiado/Comissões/Conselhos",
]


def _seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rows.extend(
        {
            "tipo": tipo,
            "peso": 1.40,
            "categoria": "Alta prioridade",
            "justificativa": "Impacto financeiro ou legal direto, com prazo legal implícito.",
            "ativo": True,
        }
        for tipo in ALTA_PRIORIDADE
    )
    rows.extend(
        {
            "tipo": tipo,
            "peso": 1.25,
            "categoria": "Prioridade média",
            "justificativa": "Controle externo ou cobrança com prazo relevante para resposta institucional.",
            "ativo": True,
        }
        for tipo in PRIORIDADE_MEDIA
    )
    rows.extend(
        {
            "tipo": tipo,
            "peso": 0.90,
            "categoria": "Rotineiro ou informativo",
            "justificativa": "Processo informativo ou rotineiro sem urgência intrínseca elevada.",
            "ativo": True,
        }
        for tipo in PESO_REDUZIDO
    )
    return rows


def upgrade() -> None:
    bind = op.get_bind()
    if "process_type_weights" not in sa.inspect(bind).get_table_names():
        return

    sql = sa.text(
        """
        INSERT INTO process_type_weights
            (tipo, peso, categoria, justificativa, ativo, created_at, updated_at)
        VALUES
            (:tipo, :peso, :categoria, :justificativa, :ativo, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (tipo) DO UPDATE SET
            peso = excluded.peso,
            categoria = excluded.categoria,
            justificativa = excluded.justificativa,
            ativo = excluded.ativo,
            updated_at = CURRENT_TIMESTAMP
        """
    )
    bind.execute(sql, _seed_rows())


def downgrade() -> None:
    bind = op.get_bind()
    if "process_type_weights" not in sa.inspect(bind).get_table_names():
        return

    tipos = [row["tipo"] for row in _seed_rows()]
    bind.execute(
        sa.text("DELETE FROM process_type_weights WHERE tipo IN :tipos").bindparams(
            sa.bindparam("tipos", expanding=True)
        ),
        {"tipos": tipos},
    )

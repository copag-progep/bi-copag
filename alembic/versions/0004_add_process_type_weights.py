"""adicionar tabela de pesos por tipo de processo

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-20 00:00:00.000000

Cria a tabela process_type_weights para configurar o multiplicador
de prioridade do Score de Risco por tipo de processo do SEI.
Tipos sem registro recebem peso implícito 1.00 (neutro).

Também corrige o único tipo em CAIXA ALTA encontrado nos dados de
produção: 'PESSOAL: AÇÕES DE DESENVOLVIMENTO EM SERVIÇO (ADS)'.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Corrigir tipo em CAIXA ALTA importado com grafia inconsistente
    op.execute(
        sa.text(
            "UPDATE processos "
            "SET tipo = 'Pessoal: Ações de Desenvolvimento em Serviço (ADS)' "
            "WHERE tipo = 'PESSOAL: AÇÕES DE DESENVOLVIMENTO EM SERVIÇO (ADS)'"
        )
    )

    # Criar tabela de pesos por tipo
    op.create_table(
        "process_type_weights",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tipo", sa.String(512), nullable=False),
        sa.Column("peso", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
        sa.Column("categoria", sa.String(100), nullable=True),
        sa.Column("justificativa", sa.Text, nullable=True),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_process_type_weights_tipo", "process_type_weights", ["tipo"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_process_type_weights_tipo", "process_type_weights")
    op.drop_table("process_type_weights")
    # Não reverte a correção de caixa — seria destrutivo restaurar texto em CAPS

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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    # Corrigir tipo em CAIXA ALTA importado com grafia inconsistente.
    # Em bancos locais novos, a tabela processos ainda pode não existir neste ponto,
    # pois o baseline é vazio e o create_all roda após as migrations.
    if "processos" in existing_tables:
        op.execute(
            sa.text(
                "UPDATE processos "
                "SET tipo = 'Pessoal: Ações de Desenvolvimento em Serviço (ADS)' "
                "WHERE tipo = 'PESSOAL: AÇÕES DE DESENVOLVIMENTO EM SERVIÇO (ADS)'"
            )
        )

    # Criar tabela de pesos por tipo
    if "process_type_weights" not in existing_tables:
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
            sa.CheckConstraint("peso >= 0.80 AND peso <= 1.50", name="ck_process_type_weights_peso"),
        )

    indexes = {idx["name"] for idx in sa.inspect(bind).get_indexes("process_type_weights")}
    if "ix_process_type_weights_tipo" not in indexes:
        op.create_index("ix_process_type_weights_tipo", "process_type_weights", ["tipo"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_process_type_weights_tipo", "process_type_weights")
    op.drop_table("process_type_weights")
    # Não reverte a correção de caixa — seria destrutivo restaurar texto em CAPS

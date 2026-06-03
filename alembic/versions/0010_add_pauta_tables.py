"""adicionar tabelas de pauta executiva prioritária

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-27 00:00:00.000000

pauta_sessoes: sessões semanais de acompanhamento de processos prioritários.
pauta_itens:   processos selecionados, com score de risco e responsável atribuído.
               Status é atualizado automaticamente após cada upload de snapshot.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "pauta_sessoes" not in existing:
        op.create_table(
            "pauta_sessoes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("titulo", sa.String(255), nullable=False),
            sa.Column("data_inicio", sa.Date, nullable=False),
            sa.Column("data_fim", sa.Date, nullable=True),
            sa.Column("data_reuniao", sa.Date, nullable=True),
            sa.Column("observacoes", sa.Text, nullable=True),
            sa.Column("ativa", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("criado_por", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_pauta_sessoes_ativa", "pauta_sessoes", ["ativa"])

    if "pauta_itens" not in existing:
        op.create_table(
            "pauta_itens",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("sessao_id", sa.Integer, sa.ForeignKey("pauta_sessoes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("protocolo", sa.String(120), nullable=False),
            sa.Column("setor", sa.String(80), nullable=False),
            sa.Column("entrada_setor", sa.Date, nullable=True),
            sa.Column("data_referencia", sa.Date, nullable=True),
            sa.Column("ultima_presenca", sa.Date, nullable=True),
            sa.Column("atribuicao", sa.String(255), nullable=True),
            sa.Column("tipo", sa.String(255), nullable=True),
            sa.Column("dias_no_setor", sa.Integer, nullable=True),
            sa.Column("score_risco", sa.Numeric(5, 3), nullable=True),
            sa.Column("nivel_risco", sa.String(20), nullable=True),
            sa.Column("assigned_to", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="pendente"),
            sa.Column("nota_admin", sa.Text, nullable=True),
            sa.Column("nota_responsavel", sa.Text, nullable=True),
            sa.Column("data_status", sa.Date, nullable=True),
            sa.Column("resolucao_automatica", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("sessao_id", "protocolo", "setor", "entrada_setor", name="uq_pauta_item"),
        )
        op.create_index("ix_pauta_itens_sessao_id", "pauta_itens", ["sessao_id"])
        op.create_index("ix_pauta_itens_protocolo", "pauta_itens", ["protocolo"])
        op.create_index("ix_pauta_itens_assigned_to", "pauta_itens", ["assigned_to"])
        op.create_index("ix_pauta_itens_status", "pauta_itens", ["status"])


def downgrade() -> None:
    op.drop_table("pauta_itens")
    op.drop_table("pauta_sessoes")

"""adicionar tabela de setores por usuário SEI (sei_user_setor)

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-27 00:00:00.000000

Vincula cada usuário SEI (atribuição/servidor) aos setores onde atua.
Usado para filtrar o dropdown de Atribuição para usuários com acesso
restrito por divisão, evitando vazamento de nomes entre divisões.

Regra do fallback (em /api/meta/options):
  - Se existir ao menos 1 vínculo explícito cadastrado → usa apenas vínculos.
  - Se não houver nenhum vínculo ainda → inferência temporária pelo histórico.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "sei_user_setor" not in existing:
        op.create_table(
            "sei_user_setor",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "sei_user_id",
                sa.Integer,
                sa.ForeignKey("sei_users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("setor", sa.String(80), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("sei_user_id", "setor", name="uq_sei_user_setor"),
        )
        op.create_index("ix_sei_user_setor_sei_user_id", "sei_user_setor", ["sei_user_id"])


def downgrade() -> None:
    op.drop_index("ix_sei_user_setor_sei_user_id", "sei_user_setor")
    op.drop_table("sei_user_setor")

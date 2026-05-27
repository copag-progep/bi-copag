"""adicionar controle de acesso por divisão (user_sector_access)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-20 00:00:00.000000

Cria a tabela user_sector_access para restringir usuários não-admin
a enxergar apenas setores específicos em todos os endpoints analíticos.

Regras de negócio:
  - Admin → sempre acesso total (tabela não é consultada)
  - Usuário sem linhas → sem acesso a dado algum (padrão seguro)
  - Usuário com linhas → só vê os setores listados
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "user_sector_access" not in existing:
        op.create_table(
            "user_sector_access",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE"),
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
            sa.UniqueConstraint("user_id", "setor", name="uq_user_sector_access"),
        )
        op.create_index("ix_user_sector_access_user_id", "user_sector_access", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_sector_access_user_id", "user_sector_access")
    op.drop_table("user_sector_access")

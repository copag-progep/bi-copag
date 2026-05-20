"""adicionar aliases historicos de usuarios SEI

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20 00:00:00.000000

Permite vincular nomes antigos ou alternativos de uma atribuicao SEI
ao mesmo usuario canonico, preservando o texto bruto importado do SEI.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sei_user_aliases" in inspector.get_table_names():
        return

    op.create_table(
        "sei_user_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sei_user_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("alias_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sei_user_id"], ["sei_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias_key", name="uq_sei_user_alias_key"),
    )
    op.create_index("ix_sei_user_aliases_id", "sei_user_aliases", ["id"])
    op.create_index("ix_sei_user_aliases_sei_user_id", "sei_user_aliases", ["sei_user_id"])
    op.create_index("ix_sei_user_aliases_alias_key", "sei_user_aliases", ["alias_key"], unique=True)
    op.create_index(
        "ix_sei_user_aliases_user_id_alias_key",
        "sei_user_aliases",
        ["sei_user_id", "alias_key"],
    )


def downgrade() -> None:
    op.drop_table("sei_user_aliases")

"""adicionar permissão de upload por usuário (can_upload)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-27 00:00:00.000000

Adiciona can_upload em users.
Padrão False para todos os usuários, inclusive os já existentes.
Admin tem acesso independente desse campo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("users")}
    if "can_upload" not in columns:
        op.add_column(
            "users",
            sa.Column("can_upload", sa.Boolean, nullable=False, server_default="false"),
        )


def downgrade() -> None:
    op.drop_column("users", "can_upload")

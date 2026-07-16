"""adicionar prazo de conclusão aos itens de pauta

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-15 00:00:00.000000

pauta_itens.prazo: data limite informada pela gestão para conclusão do
processo. Nullable — itens existentes ficam sem prazo até serem editados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("pauta_itens")}
    if "prazo" not in columns:
        op.add_column("pauta_itens", sa.Column("prazo", sa.Date, nullable=True))


def downgrade() -> None:
    op.drop_column("pauta_itens", "prazo")

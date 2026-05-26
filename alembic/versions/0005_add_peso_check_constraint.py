"""adicionar CHECK constraint no campo peso de process_type_weights

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20 00:00:00.000000

Garante integridade no banco: peso deve estar entre 0.80 e 1.50.
A validação já existia no Pydantic; este CHECK impede inserts diretos
no banco fora do range permitido.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_process_type_weights_peso",
        "process_type_weights",
        "peso >= 0.80 AND peso <= 1.50",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_process_type_weights_peso",
        "process_type_weights",
        type_="check",
    )

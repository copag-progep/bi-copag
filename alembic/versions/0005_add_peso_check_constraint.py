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
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite não suporta ALTER TABLE ADD CONSTRAINT. A constraint já é
        # criada junto da tabela na migration 0004 para bancos locais novos.
        return

    checks = {check["name"] for check in sa.inspect(bind).get_check_constraints("process_type_weights")}
    if "ck_process_type_weights_peso" in checks:
        return

    op.create_check_constraint(
        "ck_process_type_weights_peso",
        "process_type_weights",
        "peso >= 0.80 AND peso <= 1.50",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return

    checks = {check["name"] for check in sa.inspect(bind).get_check_constraints("process_type_weights")}
    if "ck_process_type_weights_peso" not in checks:
        return

    op.drop_constraint(
        "ck_process_type_weights_peso",
        "process_type_weights",
        type_="check",
    )

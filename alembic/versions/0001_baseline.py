"""baseline — schema existente antes do Alembic

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

Revisão vazia que representa o estado do banco antes da introdução do
Alembic. Bancos já existentes são selados nesta revisão automaticamente
pelo run_migrations() em database.py.
"""
from typing import Sequence, Union

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

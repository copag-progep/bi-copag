"""adicionar tabela audit_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05 00:00:00.000000

Cria a tabela de log de auditoria para registrar ações críticas
(uploads, exclusões, criação de usuários, alterações de senha, etc.).
A criação é segura em bancos existentes — verifica a existência da
tabela antes de tentar criá-la.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" in inspector.get_table_names():
        return  # já existe — nenhuma ação necessária

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=False),
        sa.Column("user_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id",         "audit_logs", ["id"])
    op.create_index("ix_audit_logs_action",      "audit_logs", ["action"])
    op.create_index("ix_audit_logs_user_email",  "audit_logs", ["user_email"])
    op.create_index("ix_audit_logs_created_at",  "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")

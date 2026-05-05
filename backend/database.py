import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "sei_bi.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs: dict = {
    "connect_args": connect_args,
    "future": True,
}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "300"))

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Executa migrações Alembic pendentes.

    Em bancos existentes que ainda não têm a tabela alembic_version,
    sela automaticamente na revisão baseline antes de aplicar qualquer
    migração nova — evitando tentar recriar tabelas que já existem.
    """
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))

        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        if existing_tables and "alembic_version" not in existing_tables:
            # Banco já existente sem controle Alembic → sela no baseline
            alembic_command.stamp(alembic_cfg, "0001")

        alembic_command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        # Não interrompe o startup se Alembic falhar — create_all cobre o caso básico
        logger.warning("Alembic migration warning: %s", exc)


def init_db() -> None:
    from . import models  # noqa: F401 — garante que todos os modelos são registrados

    run_migrations()
    Base.metadata.create_all(bind=engine)  # cria tabelas que Alembic ainda não criou
    ensure_schema_updates()
    ensure_indexes()


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if "processos" not in existing_tables:
        return

    process_columns = {column["name"] for column in inspector.get_columns("processos")}

    statements: list[str] = []
    if "atribuicao_normalizada" not in process_columns:
        statements.append("ALTER TABLE processos ADD COLUMN atribuicao_normalizada VARCHAR(255)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_indexes() -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_processos_data_relatorio_setor ON processos (data_relatorio, setor)",
        "CREATE INDEX IF NOT EXISTS ix_processos_setor_data_relatorio ON processos (setor, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_tipo_data_relatorio ON processos (tipo, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_atribuicao_data_relatorio ON processos (atribuicao, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_atribuicao_normalizada_data_relatorio ON processos (atribuicao_normalizada, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_protocolo_data_relatorio ON processos (protocolo, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_nome_key ON sei_users (nome_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_nome_sei_key ON sei_users (nome_sei_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_usuario_sei_key ON sei_users (usuario_sei_key)",
        "CREATE INDEX IF NOT EXISTS ix_monthly_stats_periodo_setor ON monthly_stats (periodo, setor)",
        "CREATE INDEX IF NOT EXISTS ix_monthly_stats_indicador_periodo ON monthly_stats (indicador, periodo)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)",
    ]
    with engine.begin() as connection:
        for statement in index_statements:
            try:
                connection.execute(text(statement))
            except Exception:
                pass  # tabela pode ainda não existir em este ponto

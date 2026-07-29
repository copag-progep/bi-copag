import logging
import os
import time
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

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_RENDER = os.getenv("RENDER", "").lower() in {"1", "true", "yes", "on"}

if IS_SQLITE:
    connect_args = {"check_same_thread": False}
else:
    statement_timeout_ms = int(os.getenv("SQLALCHEMY_STATEMENT_TIMEOUT_MS", "30000"))
    lock_timeout_ms = int(os.getenv("SQLALCHEMY_LOCK_TIMEOUT_MS", "5000"))
    connect_args = {
        "connect_timeout": int(os.getenv("SQLALCHEMY_CONNECT_TIMEOUT", "10")),
        "options": (
            f"-c statement_timeout={statement_timeout_ms} "
            f"-c lock_timeout={lock_timeout_ms}"
        ),
    }

engine_kwargs: dict = {
    "connect_args": connect_args,
    "future": True,
}
if not IS_SQLITE:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "300"))
    engine_kwargs["pool_size"] = int(os.getenv("SQLALCHEMY_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "5"))
    engine_kwargs["pool_timeout"] = 30

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def should_run_db_maintenance() -> bool:
    """Decide se migrations e manutenção estrutural rodam neste startup.

    Em ambientes locais o padrão continua ativo para facilitar o bootstrap.
    No Render, o padrão é desativado: cold starts devem apenas validar a
    conexão e abrir a API. Uma mudança de schema deve ser aplicada de forma
    controlada definindo RUN_DB_MAINTENANCE_ON_STARTUP=true temporariamente.
    """
    default = "false" if IS_RENDER else "true"
    return os.getenv("RUN_DB_MAINTENANCE_ON_STARTUP", default).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _run_startup_step(name: str, operation) -> None:
    started_at = time.monotonic()
    logger.info("Database startup step started: %s", name)
    operation()
    logger.info(
        "Database startup step completed: %s (%.2fs)",
        name,
        time.monotonic() - started_at,
    )


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def prepare_empty_database() -> None:
    """Materializa o modelo atual antes do baseline em bancos totalmente novos.

    A revisão 0001 representa um schema legado já existente e, por isso, é
    vazia. Sem esta preparação, uma instalação nova alcançaria migrations que
    consultam tabelas legadas antes do create_all executado ao final.
    """
    if inspect(engine).get_table_names():
        return
    logger.info("Empty database detected; creating current metadata baseline")
    Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    """Executa migrações Alembic pendentes.

    Em bancos existentes que ainda não têm a tabela alembic_version,
    sela automaticamente na revisão baseline antes de aplicar qualquer
    migração nova — evitando tentar recriar tabelas que já existem.
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    alembic_cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    if existing_tables and "alembic_version" not in existing_tables:
        # Banco já existente sem controle Alembic → sela no baseline
        logger.info("Alembic version table missing; stamping baseline 0001")
        alembic_command.stamp(alembic_cfg, "0001")

    logger.info("Applying Alembic migrations up to head")
    alembic_command.upgrade(alembic_cfg, "head")


def init_db() -> None:
    from . import models  # noqa: F401 — garante que todos os modelos são registrados

    _run_startup_step("connection_check", check_database_connection)
    if not should_run_db_maintenance():
        logger.info(
            "Database structural maintenance skipped "
            "(RUN_DB_MAINTENANCE_ON_STARTUP=false)"
        )
        return

    _run_startup_step("empty_database_bootstrap", prepare_empty_database)
    _run_startup_step("alembic_migrations", run_migrations)
    _run_startup_step(
        "metadata_create_all",
        lambda: Base.metadata.create_all(bind=engine),
    )
    _run_startup_step("schema_updates", ensure_schema_updates)
    _run_startup_step("index_updates", ensure_indexes)


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
        # Índice de cobertura para as queries analíticas principais — evita heap fetch por linha
        "CREATE INDEX IF NOT EXISTS ix_processos_covering_analytics ON processos (setor, data_relatorio, protocolo, atribuicao_normalizada, tipo)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_nome_key ON sei_users (nome_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_nome_sei_key ON sei_users (nome_sei_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_users_usuario_sei_key ON sei_users (usuario_sei_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_user_aliases_sei_user_id ON sei_user_aliases (sei_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_sei_user_aliases_alias_key ON sei_user_aliases (alias_key)",
        "CREATE INDEX IF NOT EXISTS ix_sei_user_aliases_user_id_alias_key ON sei_user_aliases (sei_user_id, alias_key)",
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

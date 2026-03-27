import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "sei_bi.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs = {
    "connect_args": connect_args,
    "future": True,
    "pool_pre_ping": True,
}
if not DATABASE_URL.startswith("sqlite"):
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


def init_db() -> None:
    from . import models

    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    ensure_indexes()


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
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
    ]
    with engine.begin() as connection:
        for statement in index_statements:
            connection.execute(text(statement))

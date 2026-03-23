import os
from pathlib import Path

from sqlalchemy import create_engine, text
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
    ensure_indexes()


def ensure_indexes() -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_processos_data_relatorio_setor ON processos (data_relatorio, setor)",
        "CREATE INDEX IF NOT EXISTS ix_processos_setor_data_relatorio ON processos (setor, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_tipo_data_relatorio ON processos (tipo, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_atribuicao_data_relatorio ON processos (atribuicao, data_relatorio)",
        "CREATE INDEX IF NOT EXISTS ix_processos_protocolo_data_relatorio ON processos (protocolo, data_relatorio)",
    ]
    with engine.begin() as connection:
        for statement in index_statements:
            connection.execute(text(statement))

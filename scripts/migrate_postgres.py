import argparse
import os
from collections.abc import Iterable

from sqlalchemy import MetaData, create_engine, func, inspect, select, text

from backend.models import Processo, Upload, User


TABLES = [User.__table__, Upload.__table__, Processo.__table__]
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_processos_data_relatorio_setor ON processos (data_relatorio, setor)",
    "CREATE INDEX IF NOT EXISTS ix_processos_setor_data_relatorio ON processos (setor, data_relatorio)",
    "CREATE INDEX IF NOT EXISTS ix_processos_tipo_data_relatorio ON processos (tipo, data_relatorio)",
    "CREATE INDEX IF NOT EXISTS ix_processos_atribuicao_data_relatorio ON processos (atribuicao, data_relatorio)",
    "CREATE INDEX IF NOT EXISTS ix_processos_protocolo_data_relatorio ON processos (protocolo, data_relatorio)",
]


def normalize_url(url: str) -> str:
    return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url


def build_engine(url: str):
    normalized = normalize_url(url)
    connect_args = {"check_same_thread": False} if normalized.startswith("sqlite") else {}
    engine_kwargs = {
        "connect_args": connect_args,
        "future": True,
        "pool_pre_ping": True,
    }
    if not normalized.startswith("sqlite"):
        engine_kwargs["pool_recycle"] = int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "300"))
    return create_engine(normalized, **engine_kwargs)


def ensure_target_schema(target_engine) -> None:
    metadata = MetaData()
    for table in TABLES:
        table.to_metadata(metadata)
    metadata.create_all(target_engine)
    with target_engine.begin() as connection:
        for statement in INDEX_STATEMENTS:
            connection.execute(text(statement))


def validate_tables(source_engine) -> None:
    inspector = inspect(source_engine)
    existing_tables = set(inspector.get_table_names())
    expected = {table.name for table in TABLES}
    missing = expected.difference(existing_tables)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise RuntimeError(f"Banco de origem sem as tabelas esperadas: {missing_list}")


def table_row_count(engine, table) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def abort_if_target_not_empty(target_engine) -> None:
    for table in TABLES:
        if table_row_count(target_engine, table) > 0:
            raise RuntimeError(
                "O banco de destino ja possui dados. Use --truncate-target se quiser limpar o destino antes da copia."
            )


def truncate_target(target_engine) -> None:
    with target_engine.begin() as connection:
        for table in reversed(TABLES):
            connection.execute(table.delete())


def batched_rows(result, batch_size: int) -> Iterable[list[dict]]:
    while True:
        rows = result.mappings().fetchmany(batch_size)
        if not rows:
            return
        yield [dict(row) for row in rows]


def copy_table(source_engine, target_engine, table, batch_size: int) -> int:
    copied = 0
    with source_engine.connect() as source_connection:
        result = source_connection.execution_options(stream_results=True).execute(select(table))
        for batch in batched_rows(result, batch_size):
            with target_engine.begin() as target_connection:
                target_connection.execute(table.insert(), batch)
            copied += len(batch)
    return copied


def sync_postgres_sequences(target_engine) -> None:
    if not str(target_engine.url).startswith("postgresql"):
        return

    statements = [
        """
        SELECT setval(
            pg_get_serial_sequence('users', 'id'),
            COALESCE((SELECT MAX(id) FROM users), 1),
            COALESCE((SELECT MAX(id) FROM users), 0) > 0
        )
        """,
        """
        SELECT setval(
            pg_get_serial_sequence('uploads', 'id'),
            COALESCE((SELECT MAX(id) FROM uploads), 1),
            COALESCE((SELECT MAX(id) FROM uploads), 0) > 0
        )
        """,
        """
        SELECT setval(
            pg_get_serial_sequence('processos', 'id'),
            COALESCE((SELECT MAX(id) FROM processos), 1),
            COALESCE((SELECT MAX(id) FROM processos), 0) > 0
        )
        """,
    ]
    with target_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copia os dados do SEI BI entre dois bancos compativeis com SQLAlchemy."
    )
    parser.add_argument("--source-url", default=os.getenv("SOURCE_DATABASE_URL"))
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--truncate-target", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source_url or not args.target_url:
        raise RuntimeError(
            "Informe SOURCE_DATABASE_URL e TARGET_DATABASE_URL (ou DATABASE_URL), ou passe --source-url e --target-url."
        )

    source_url = normalize_url(args.source_url)
    target_url = normalize_url(args.target_url)
    if source_url == target_url:
        raise RuntimeError("Origem e destino apontam para o mesmo banco.")

    source_engine = build_engine(source_url)
    target_engine = build_engine(target_url)

    validate_tables(source_engine)
    ensure_target_schema(target_engine)

    if args.truncate_target:
        truncate_target(target_engine)
    else:
        abort_if_target_not_empty(target_engine)

    print(f"Origem: {source_engine.url.render_as_string(hide_password=True)}")
    print(f"Destino: {target_engine.url.render_as_string(hide_password=True)}")

    for table in TABLES:
        total = table_row_count(source_engine, table)
        print(f"Copiando {table.name}: {total} registro(s)")
        copied = copy_table(source_engine, target_engine, table, args.batch_size)
        print(f"Concluido {table.name}: {copied} registro(s)")

    sync_postgres_sequences(target_engine)
    print("Migracao concluida com sucesso.")


if __name__ == "__main__":
    main()

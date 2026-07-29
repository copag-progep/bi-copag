"""Testes da política de manutenção estrutural no startup."""

from backend import database


def test_render_skips_db_maintenance_by_default(monkeypatch):
    monkeypatch.setattr(database, "IS_RENDER", True)
    monkeypatch.delenv("RUN_DB_MAINTENANCE_ON_STARTUP", raising=False)

    assert database.should_run_db_maintenance() is False


def test_local_runs_db_maintenance_by_default(monkeypatch):
    monkeypatch.setattr(database, "IS_RENDER", False)
    monkeypatch.delenv("RUN_DB_MAINTENANCE_ON_STARTUP", raising=False)

    assert database.should_run_db_maintenance() is True


def test_explicit_setting_overrides_environment_default(monkeypatch):
    monkeypatch.setattr(database, "IS_RENDER", True)
    monkeypatch.setenv("RUN_DB_MAINTENANCE_ON_STARTUP", "true")
    assert database.should_run_db_maintenance() is True

    monkeypatch.setattr(database, "IS_RENDER", False)
    monkeypatch.setenv("RUN_DB_MAINTENANCE_ON_STARTUP", "false")
    assert database.should_run_db_maintenance() is False


def test_init_db_skips_structural_steps_when_maintenance_is_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(database, "should_run_db_maintenance", lambda: False)
    monkeypatch.setattr(
        database,
        "check_database_connection",
        lambda: calls.append("connection_check"),
    )
    monkeypatch.setattr(
        database,
        "prepare_empty_database",
        lambda: calls.append("empty_database_bootstrap"),
    )
    monkeypatch.setattr(
        database,
        "run_migrations",
        lambda: calls.append("alembic_migrations"),
    )
    monkeypatch.setattr(
        database,
        "ensure_schema_updates",
        lambda: calls.append("schema_updates"),
    )
    monkeypatch.setattr(
        database,
        "ensure_indexes",
        lambda: calls.append("index_updates"),
    )

    database.init_db()

    assert calls == ["connection_check"]

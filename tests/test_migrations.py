import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_initial_migration():
    path = REPO_ROOT / "apps" / "api" / "alembic" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_tenant_table_has_rls_contract() -> None:
    migration = load_initial_migration()
    assert migration.GLOBAL_TABLES == {"tenants", "users"}
    assert "events" in migration.TABLES
    for name in migration.TABLES:
        if name not in migration.GLOBAL_TABLES:
            assert name.isidentifier(), f"unsafe SQL table name: {name}"


def test_join_tables_have_one_primary_key_and_unique_scope() -> None:
    migration = load_initial_migration()
    for name in ("memberships", "agent_tools"):
        definition = migration.TABLES[name].lower()
        assert "primary key" not in definition
        assert "unique(" in definition


def test_required_phase_zero_tables_exist() -> None:
    migration = load_initial_migration()
    required = {
        "tenants", "users", "memberships", "agents", "agent_versions", "calls",
        "call_turns", "call_events", "knowledge_bases", "documents", "chunks", "tools",
    }
    assert required <= set(migration.TABLES)

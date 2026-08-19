"""Enforce tenant isolation for application database roles."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'voiceos_app') "
        "THEN CREATE ROLE voiceos_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO voiceos_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO voiceos_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voiceos_app")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO voiceos_app")
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON tenants "
        "USING (id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (id = nullif(current_setting('app.tenant_id', true), '')::uuid)"
    )
    scoped = op.get_bind().exec_driver_sql(
        "SELECT tablename FROM pg_policies WHERE schemaname='public' AND policyname='tenant_isolation' AND tablename <> 'tenants'"
    ).scalars()
    for table in scoped:
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER POLICY tenant_isolation ON "{table}" WITH CHECK (tenant_id = nullif(current_setting(\'app.tenant_id\', true), \'\')::uuid)')


def downgrade() -> None:
    scoped = op.get_bind().exec_driver_sql(
        "SELECT tablename FROM pg_policies WHERE schemaname='public' AND policyname='tenant_isolation'"
    ).scalars()
    for table in scoped:
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenants")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")

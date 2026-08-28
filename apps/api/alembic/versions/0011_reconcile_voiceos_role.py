"""Reconcile the application role after database-only restores."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'voiceos_app') "
        "THEN CREATE ROLE voiceos_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
        "NOBYPASSRLS; END IF; END $$"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO voiceos_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO voiceos_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voiceos_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO voiceos_app"
    )


def downgrade() -> None:
    # The role is cluster-wide and may be shared by another restored database.
    # Removing it during an application rollback would be unsafe.
    pass

"""Idempotent billing usage threshold alerts.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE billing_usage_alerts (id uuid primary key default gen_random_uuid(), tenant_id uuid not null, period date not null, threshold int not null, minutes int not null, created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(tenant_id,period,threshold))"
    )
    op.execute("ALTER TABLE billing_usage_alerts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE billing_usage_alerts FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON billing_usage_alerts USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE billing_usage_alerts")

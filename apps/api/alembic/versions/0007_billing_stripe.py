"""Complete Stripe billing identifiers and reconciliation indexes."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE plans ADD COLUMN stripe_overage_price_id text")
    op.execute("ALTER TABLE plans ADD COLUMN stripe_phone_price_id text")
    op.create_unique_constraint(
        "subscriptions_stripe_subscription_id_key",
        "subscriptions",
        ["stripe_subscription_id"],
    )
    op.create_unique_constraint("invoices_stripe_invoice_id_key", "invoices", ["stripe_invoice_id"])
    op.create_index("ix_usage_records_tenant_period", "usage_records", ["tenant_id", "period"])


def downgrade() -> None:
    op.drop_index("ix_usage_records_tenant_period", table_name="usage_records")
    op.drop_constraint("subscriptions_stripe_subscription_id_key", "subscriptions", type_="unique")
    op.drop_constraint("invoices_stripe_invoice_id_key", "invoices", type_="unique")
    op.execute("ALTER TABLE plans DROP COLUMN stripe_phone_price_id")
    op.execute("ALTER TABLE plans DROP COLUMN stripe_overage_price_id")

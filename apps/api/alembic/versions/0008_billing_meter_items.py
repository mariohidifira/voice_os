"""Track Stripe metered and phone subscription items."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscriptions ADD COLUMN stripe_overage_item_id text")
    op.execute("ALTER TABLE subscriptions ADD COLUMN stripe_phone_item_id text")
    op.execute("ALTER TABLE subscriptions ADD COLUMN past_due_since timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE subscriptions DROP COLUMN past_due_since")
    op.execute("ALTER TABLE subscriptions DROP COLUMN stripe_phone_item_id")
    op.execute("ALTER TABLE subscriptions DROP COLUMN stripe_overage_item_id")

"""Ensure one provider integration per tenant."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_integrations_tenant_provider", "integrations", ["tenant_id", "provider"])


def downgrade() -> None:
    op.drop_constraint("uq_integrations_tenant_provider", "integrations", type_="unique")

"""Add tenant-scoped identities used by session end-user upserts."""

from alembic import op
from sqlalchemy import text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_end_users_tenant_external_id",
        "end_users",
        ["tenant_id", "external_id"],
        unique=True,
        postgresql_where=text("external_id IS NOT NULL"),
    )
    op.create_index(
        "uq_end_users_tenant_phone",
        "end_users",
        ["tenant_id", "phone"],
        unique=True,
        postgresql_where=text("phone IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_end_users_tenant_phone", table_name="end_users")
    op.drop_index("uq_end_users_tenant_external_id", table_name="end_users")

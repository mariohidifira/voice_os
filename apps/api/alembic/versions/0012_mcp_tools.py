"""Add MCP configuration to the existing tenant-scoped tools table."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tools ADD COLUMN IF NOT EXISTS mcp jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE tools DROP COLUMN IF EXISTS mcp")

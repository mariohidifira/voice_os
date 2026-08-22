"""Allow a released phone number to be purchased again."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("phone_numbers_e164_key", "phone_numbers", type_="unique")
    op.create_index(
        "uq_phone_numbers_active_e164",
        "phone_numbers",
        ["e164"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_phone_numbers_active_e164", table_name="phone_numbers")
    op.create_unique_constraint("phone_numbers_e164_key", "phone_numbers", ["e164"])

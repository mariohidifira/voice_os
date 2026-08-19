"""Auth.js PostgreSQL adapter tables."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS "emailVerified" timestamptz')
    op.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS image text')
    op.execute("CREATE TABLE accounts (id uuid primary key default gen_random_uuid(), \"userId\" uuid not null references users(id) on delete cascade, type text not null, provider text not null, \"providerAccountId\" text not null, refresh_token text, access_token text, expires_at bigint, token_type text, scope text, id_token text, session_state text, unique(provider,\"providerAccountId\"))")
    op.execute("CREATE TABLE sessions (id uuid primary key default gen_random_uuid(), \"sessionToken\" text unique not null, \"userId\" uuid not null references users(id) on delete cascade, expires timestamptz not null)")
    op.execute("CREATE TABLE verification_token (identifier text not null, token text not null, expires timestamptz not null, primary key(identifier,token))")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS verification_token")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS accounts")
    op.execute('ALTER TABLE users DROP COLUMN IF EXISTS image')
    op.execute('ALTER TABLE users DROP COLUMN IF EXISTS "emailVerified"')

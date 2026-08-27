"""WhatsApp queue and conversation simulator.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE integrations ADD COLUMN config jsonb NOT NULL DEFAULT '{}'::jsonb")
    op.execute("CREATE TABLE whatsapp_messages (id uuid primary key default gen_random_uuid(), tenant_id uuid not null, call_id uuid, provider_message_id text unique not null, direction text not null, type text not null, text text, media_id text, status text not null default 'pending', payload jsonb not null default '{}'::jsonb, error text, created_at timestamptz not null default now(), updated_at timestamptz not null default now())")
    op.execute("CREATE TABLE simulations (id uuid primary key default gen_random_uuid(), tenant_id uuid not null, agent_id uuid not null, persona text not null, objective text not null, conversation_count int not null, status text not null default 'pending', report jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now())")
    for table in ("whatsapp_messages", "simulations"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)")
    op.execute("CREATE INDEX whatsapp_messages_queue ON whatsapp_messages(status,created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE simulations")
    op.execute("DROP TABLE whatsapp_messages")
    op.execute("ALTER TABLE integrations DROP COLUMN config")

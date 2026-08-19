"""Complete VoiceOS v1 schema and tenant isolation."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = {
    "tenants": "slug text unique not null, name text not null, status text not null default 'trial', settings jsonb not null default '{}'::jsonb, stripe_customer_id text, deleted_at timestamptz",
    "users": "email text unique not null, name text, avatar_url text, is_platform_admin boolean not null default false, last_login_at timestamptz",
    "memberships": "user_id uuid not null references users(id), role text not null, unique(user_id,tenant_id)",
    "agents": "name text not null, status text not null default 'draft', current_version_id uuid, draft_version_id uuid, deleted_at timestamptz",
    "agent_versions": "agent_id uuid not null references agents(id), version int not null, published_at timestamptz, system_prompt text not null, greeting text not null, language text not null default 'pt-BR', extra_languages text[] not null default '{}', llm jsonb not null default '{}'::jsonb, stt jsonb not null default '{}'::jsonb, tts jsonb not null default '{}'::jsonb, turn_config jsonb not null default '{}'::jsonb, behavior jsonb not null default '{}'::jsonb, knowledge_base_id uuid, rag jsonb not null default '{}'::jsonb, variables jsonb not null default '{}'::jsonb, created_by uuid",
    "phone_numbers": "agent_id uuid, e164 text unique not null, provider text not null default 'twilio', provider_sid text, capabilities jsonb not null default '{}'::jsonb, status text not null default 'active', livekit_dispatch_rule_id text",
    "knowledge_bases": "name text not null, embedding_model text not null default 'text-embedding-3-small', chunk_size int not null default 800, chunk_overlap int not null default 120, status text not null default 'ready'",
    "documents": "knowledge_base_id uuid not null, name text not null, source_type text not null, source_uri text, s3_key text, mime text, size_bytes bigint, status text not null default 'pending', error text, chunk_count int not null default 0, checksum text, deleted_at timestamptz",
    "chunks": "document_id uuid not null, knowledge_base_id uuid not null, ordinal int not null, content text not null, embedding vector(1536), metadata jsonb not null default '{}'::jsonb, token_count int not null default 0",
    "tools": "name text not null, description text not null, type text not null, native_kind text, parameters_schema jsonb not null, webhook jsonb, speak_before text, is_async boolean not null default false, last_test_ok_at timestamptz, unique(tenant_id,name)",
    "agent_tools": "agent_version_id uuid not null, tool_id uuid not null, enabled boolean not null default true, unique(agent_version_id,tool_id)",
    "secrets": "name text not null, ciphertext bytea not null, kms_key_id text not null, rotated_at timestamptz",
    "integrations": "provider text not null, scopes text[] not null default '{}', refresh_token_secret_id uuid, account_email text, status text not null",
    "end_users": "external_id text, phone text, email text, name text, metadata jsonb not null default '{}'::jsonb, first_seen_at timestamptz, last_seen_at timestamptz",
    "calls": "agent_id uuid not null, agent_version_id uuid, channel text not null, status text not null, end_reason text, end_user_id uuid, from_number text, to_number text, livekit_room text, provider_call_sid text, campaign_id uuid, started_at timestamptz, answered_at timestamptz, ended_at timestamptz, duration_s int, billable_seconds int, cost jsonb not null default '{}'::jsonb, latency jsonb not null default '{}'::jsonb, summary text, outcome jsonb not null default '{}'::jsonb, variables jsonb not null default '{}'::jsonb, metadata jsonb not null default '{}'::jsonb",
    "call_turns": "call_id uuid not null, ordinal int not null, role text not null, text text not null, started_at timestamptz, ended_at timestamptz, interrupted boolean not null default false, ttfb_ms int, stt_confidence double precision, audio_offset_ms int not null default 0",
    "call_tool_calls": "call_id uuid not null, turn_id uuid, tool_id uuid, name text not null, arguments jsonb not null, result jsonb, status text not null, duration_ms int, started_at timestamptz",
    "call_events": "call_id uuid not null, type text not null, payload jsonb not null default '{}'::jsonb, at timestamptz not null",
    "call_recordings": "call_id uuid unique not null, s3_key text not null, format text not null, duration_s int, size_bytes bigint, expires_at timestamptz, status text not null",
    "call_qa": "call_id uuid unique not null, score int not null, rubric jsonb not null, issues text[] not null default '{}', model text not null",
    "campaigns": "agent_id uuid not null, name text not null, status text not null default 'draft', schedule jsonb not null, stats jsonb not null default '{}'::jsonb",
    "campaign_contacts": "campaign_id uuid not null, phone text not null, name text, variables jsonb not null default '{}'::jsonb, status text not null default 'pending', attempts int not null default 0, last_call_id uuid, next_attempt_at timestamptz",
    "api_keys": "name text not null, prefix text not null, hash text not null, scope text not null, allowed_origins text[] not null default '{}', last_used_at timestamptz, revoked_at timestamptz",
    "webhooks_out": "url text not null, events text[] not null, secret_id uuid, enabled boolean not null default true",
    "webhook_deliveries": "webhook_id uuid not null, event text not null, payload jsonb not null, status text not null, attempts int not null default 0, last_status_code int, next_retry_at timestamptz",
    "subscriptions": "plan_id uuid not null, stripe_subscription_id text, status text not null, current_period_start timestamptz, current_period_end timestamptz, cancel_at timestamptz",
    "usage_records": "call_id uuid unique not null, period date not null, billable_seconds int not null, channel text not null, cost_usd numeric(12,4) not null default 0, stripe_usage_record_id text",
    "invoices": "stripe_invoice_id text not null, period_start timestamptz, period_end timestamptz, amount_cents int not null, status text not null, pdf_url text",
    "events": "actor_type text not null, actor_id text, type text not null, entity_type text, entity_id uuid, payload jsonb not null default '{}'::jsonb, at timestamptz not null default now()",
    "exports": "type text not null, filters jsonb not null, status text not null default 'pending', s3_key text, expires_at timestamptz",
    "do_not_call": "phone text not null, reason text, unique(tenant_id,phone)",
    "whatsapp_templates": "name text not null, language text not null, status text not null, provider_id text"
}

GLOBAL_TABLES = {"tenants", "users"}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE TABLE plans (id uuid primary key default gen_random_uuid(), code text unique not null, name text not null, monthly_price_cents int not null, included_minutes int not null, overage_cents_per_min int not null, max_agents int, max_concurrent_calls int, features jsonb not null default '{}'::jsonb, stripe_price_id text, created_at timestamptz not null default now(), updated_at timestamptz not null default now())")
    for name, columns in TABLES.items():
        tenant = "" if name in GLOBAL_TABLES else ("tenant_id uuid," if name == "events" else "tenant_id uuid not null,")
        op.execute(f"CREATE TABLE {name} (id uuid primary key default gen_random_uuid(), {tenant} {columns}, created_at timestamptz not null default now(), updated_at timestamptz not null default now())")
        if name not in GLOBAL_TABLES:
            op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant_isolation ON {name} USING (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid)")
    op.execute("CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX calls_tenant_started ON calls(tenant_id,started_at DESC)")


def downgrade() -> None:
    for name in reversed(list(TABLES)):
        op.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
    op.execute("DROP TABLE IF EXISTS plans CASCADE")

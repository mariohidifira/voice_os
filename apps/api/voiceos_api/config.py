from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "dev"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8005"
    database_url: str = "postgresql+asyncpg://voiceos:voiceos@localhost:5432/voiceos"
    redis_url: str = "redis://localhost:6379/0"
    s3_bucket_recordings: str = "voiceos-recordings"
    s3_bucket_documents: str = "voiceos-documents"
    s3_bucket_exports: str = "voiceos-exports"
    auth_secret: str = "dev-secret-change-me-at-least-32-bytes"
    jwt_issuer: str = "voiceos"
    jwt_audience: str = "voiceos-api"
    internal_api_token: str = "dev-internal-token"
    livekit_url: str = "wss://example.invalid"
    livekit_api_key: str = "dev"
    livekit_api_secret: str = "dev"
    livekit_sip_trunk_id_inbound: str = ""
    livekit_sip_trunk_id_outbound: str = ""
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_messaging_service_sid: str | None = None
    deepgram_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    anthropic_postprocess_model: str = "claude-haiku-4-5"
    aws_kms_key_id: str | None = None
    aws_region: str = "sa-east-1"
    resend_api_key: str | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_graph_version: str = "v23.0"
    email_from: str = "VoiceOS <noreply@example.invalid>"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8005/v1/integrations/google/callback"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    sentry_dsn: str | None = None
    # MCP stays opt-in globally. A tenant tool also needs explicit approval before it
    # can be exposed to an agent or invoked.
    mcp_enabled: bool = False
    mcp_allowed_hosts: str = ""
    mcp_allow_private_network: bool = False


def validate_runtime_settings(settings: Settings) -> None:
    """Fail fast on placeholder or default secrets in non-development environments."""
    if settings.app_env.lower() in {"dev", "test"}:
        return
    errors: list[str] = []
    if not settings.livekit_url.startswith(("wss://", "ws://")) or ".invalid" in settings.livekit_url:
        errors.append("LIVEKIT_URL must be a real ws(s):// endpoint")
    if not settings.livekit_api_key or settings.livekit_api_key == "dev":
        errors.append("LIVEKIT_API_KEY is required")
    if not settings.livekit_api_secret or settings.livekit_api_secret == "dev":
        errors.append("LIVEKIT_API_SECRET is required")
    if len(settings.auth_secret.encode()) < 32 or settings.auth_secret == "dev-secret-change-me-at-least-32-bytes":
        errors.append("AUTH_SECRET must be a unique value of at least 32 bytes")
    if not settings.internal_api_token or settings.internal_api_token == "dev-internal-token":
        errors.append("INTERNAL_API_TOKEN is required")
    if ".invalid" in settings.app_base_url or ".invalid" in settings.api_base_url:
        errors.append("APP_BASE_URL/API_BASE_URL cannot use a placeholder domain")
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()

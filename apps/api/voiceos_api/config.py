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
    openai_api_key: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

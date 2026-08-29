import os

from voiceos_voice.livekit_worker import run


def validate_worker_settings() -> None:
    """Fail fast before registering a worker with an unusable production config."""
    if os.getenv("APP_ENV", "dev").lower() in {"dev", "test"}:
        return
    errors: list[str] = []
    livekit_url = os.getenv("LIVEKIT_URL", "")
    if not livekit_url.startswith(("wss://", "ws://")) or ".invalid" in livekit_url:
        errors.append("LIVEKIT_URL must be a real ws(s):// endpoint")
    if not os.getenv("LIVEKIT_API_KEY") or os.getenv("LIVEKIT_API_KEY") == "dev":
        errors.append("LIVEKIT_API_KEY is required")
    if not os.getenv("LIVEKIT_API_SECRET") or os.getenv("LIVEKIT_API_SECRET") == "dev":
        errors.append("LIVEKIT_API_SECRET is required")
    if not os.getenv("INTERNAL_API_TOKEN") or os.getenv("INTERNAL_API_TOKEN") == "dev-internal-token":
        errors.append("INTERNAL_API_TOKEN is required")
    if errors:
        raise RuntimeError("Invalid production worker configuration: " + "; ".join(errors))

if __name__ == "__main__":
    validate_worker_settings()
    run()

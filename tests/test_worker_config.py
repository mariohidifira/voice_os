import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def worker_main(monkeypatch):
    for key in (
        "APP_ENV",
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "INTERNAL_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    path = Path(__file__).parents[1] / "apps" / "agent-worker" / "livekit_main.py"
    spec = importlib.util.spec_from_file_location("voiceos_test_livekit_main", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_allows_development_defaults(worker_main, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    worker_main.validate_worker_settings()


def test_worker_rejects_placeholder_production_config(worker_main, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.invalid")
    monkeypatch.setenv("LIVEKIT_API_KEY", "dev")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "dev")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "dev-internal-token")

    with pytest.raises(RuntimeError, match="Invalid production worker configuration"):
        worker_main.validate_worker_settings()


def test_worker_accepts_complete_production_config(worker_main, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LIVEKIT_URL", "wss://livekit.example.com")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "token")

    worker_main.validate_worker_settings()

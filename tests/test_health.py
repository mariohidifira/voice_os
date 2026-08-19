from typing import Any

import pytest
import voiceos_api.health as health_module
from voiceos_api.config import Settings
from voiceos_api.health import HealthChecker, get_health_checker


class FakeConnection:
    async def execute(self, statement: Any) -> None:
        assert statement is not None


class FakeConnectionContext:
    async def __aenter__(self) -> FakeConnection:
        return FakeConnection()

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnectionContext:
        return FakeConnectionContext()


class FakeRedis:
    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_deep_health_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "engine", FakeEngine())
    monkeypatch.setattr(health_module.Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    result = await HealthChecker(Settings()).check()
    assert result["status"] == "ok"
    assert all(result["components"].values())


def test_health_factory() -> None:
    assert isinstance(get_health_checker(), HealthChecker)


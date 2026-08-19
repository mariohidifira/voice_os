import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    window_s: float = 60
    recovery_s: float = 120
    failures: list[float] = field(default_factory=list, init=False)
    opened_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")

    @property
    def state(self) -> CircuitState:
        if self.opened_at is None:
            return CircuitState.CLOSED
        if time.monotonic() - self.opened_at >= self.recovery_s:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def allow(self) -> None:
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError("provider circuit is open")

    def success(self) -> None:
        self.failures.clear()
        self.opened_at = None

    def failure(self) -> None:
        now = time.monotonic()
        self.failures = [value for value in self.failures if now - value <= self.window_s]
        self.failures.append(now)
        if len(self.failures) >= self.failure_threshold:
            self.opened_at = now


async def resilient_call[T](
    primary: Callable[[], Awaitable[T]],
    fallback: Callable[[], Awaitable[T]],
    *,
    breaker: CircuitBreaker,
    timeout_s: float,
    retries: int = 1,
) -> tuple[T, bool]:
    try:
        breaker.allow()
    except CircuitOpenError:
        async with asyncio.timeout(timeout_s):
            return await fallback(), True
    for attempt in range(retries + 1):
        try:
            async with asyncio.timeout(timeout_s):
                result = await primary()
            breaker.success()
            return result, False
        except (TimeoutError, OSError, RuntimeError):
            breaker.failure()
            if attempt < retries:
                await asyncio.sleep(0.05 * (2**attempt))
    async with asyncio.timeout(timeout_s):
        return await fallback(), True

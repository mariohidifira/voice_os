import asyncio
from typing import Any

from jsonschema import Draft202012Validator

from .contracts import ToolCall, ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self.handlers: dict[str, ToolHandler] = {}
        self.schemas: dict[str, dict[str, Any]] = {}

    def register(self, name: str, schema: dict[str, Any], handler: ToolHandler) -> None:
        self.schemas[name] = schema
        self.handlers[name] = handler

    async def execute(self, call: ToolCall, *, timeout_s: float = 8) -> dict[str, Any]:
        if call.name not in self.handlers:
            return {"error": "unknown_tool"}
        errors = list(Draft202012Validator(self.schemas[call.name]).iter_errors(call.arguments))
        if errors:
            return {"error": "invalid_arguments", "details": [error.message for error in errors]}
        try:
            async with asyncio.timeout(timeout_s):
                return await self.handlers[call.name](call.arguments)
        except TimeoutError:
            return {"error": "timeout"}
        except Exception as exc:
            return {"error": "execution_failed", "message": str(exc)}

    async def execute_many(self, calls: tuple[ToolCall, ...]) -> list[dict[str, Any]]:
        return await asyncio.gather(*(self.execute(call) for call in calls))

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .api_client import WorkerAPI
from .contracts import LLMProvider, RAGProvider, TTSProvider, VoiceEvent
from .prompting import build_system_prompt
from .session import VoiceSession
from .tools import ToolRegistry


class APIRAG(RAGProvider):
    def __init__(self, api: WorkerAPI, knowledge_base_id: UUID) -> None:
        self.api = api
        self.knowledge_base_id = knowledge_base_id

    async def query(self, text: str, *, top_k: int, min_score: float) -> list[str]:
        rows = await self.api.query_knowledge(
            self.knowledge_base_id, text, top_k=top_k, min_score=min_score
        )
        return [str(row["content"]) for row in rows if row.get("content")]


@dataclass
class RuntimeSession:
    api: WorkerAPI
    call_id: UUID
    runtime: dict[str, Any]
    voice: VoiceSession
    _ordinal: int = 0

    @classmethod
    async def create(
        cls,
        api: WorkerAPI,
        agent_id: UUID,
        primary_llm: LLMProvider,
        fallback_llm: LLMProvider,
        primary_tts: TTSProvider,
        fallback_tts: TTSProvider,
        *,
        version: str = "current",
        channel: str = "web",
        livekit_room: str | None = None,
        variables: dict[str, Any] | None = None,
        end_user: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RuntimeSession":
        runtime = await api.runtime(agent_id, version)
        initial_variables = {**runtime.get("variables", {}), **(variables or {})}
        created = await api.create_call(
            {
                "tenant_id": runtime["tenant_id"],
                "agent_id": str(agent_id),
                "agent_version_id": runtime["version_id"],
                "channel": channel,
                "livekit_room": livekit_room,
                "variables": initial_variables,
                "metadata": metadata or {},
            }
        )
        call_id = UUID(str(created["id"]))
        registry = ToolRegistry()

        for tool in runtime.get("tools", []):
            tool_id = str(tool["id"])

            async def execute(arguments: dict[str, Any], *, remote_tool_id: str = tool_id) -> dict[str, Any]:
                return await api.execute_tool(
                    {
                        "tool_id": remote_tool_id,
                        "call_id": str(call_id),
                        "arguments": arguments,
                        "session_variables": initial_variables,
                        "end_user": end_user or {},
                    }
                )

            registry.register(str(tool["name"]), dict(tool.get("parameters_schema") or {"type": "object"}), execute)

        async def event_sink(event: VoiceEvent) -> None:
            await api.append_events(
                call_id,
                [{"type": event.type, "payload": event.payload, "at": datetime.now(UTC).isoformat()}],
            )

        rag = APIRAG(api, UUID(str(runtime["knowledge_base_id"]))) if runtime.get("knowledge_base_id") else None
        prompt = build_system_prompt(
            {"id": runtime["tenant_id"]},
            runtime,
            channel=channel,
            variables=initial_variables,
            end_user=end_user,
            tools=list(runtime.get("tools", [])),
            now=datetime.now(UTC),
        )
        voice = VoiceSession(
            primary_llm,
            fallback_llm,
            primary_tts,
            fallback_tts,
            registry,
            prompt,
            rag=rag,
            event_sink=event_sink,
            variables=initial_variables,
        )
        await api.update_call(call_id, {"status": "in_progress", "answered_at": datetime.now(UTC).isoformat()})
        return cls(api, call_id, runtime, voice)

    async def turn(self, text: str) -> tuple[str, list[bytes]]:
        started_at = datetime.now(UTC)
        reply, audio = await self.voice.turn(text)
        turns = [
            {"ordinal": self._ordinal, "role": "user", "text": text, "started_at": started_at.isoformat()},
            {"ordinal": self._ordinal + 1, "role": "assistant", "text": reply, "started_at": datetime.now(UTC).isoformat()},
        ]
        self._ordinal += 2
        await self.api.append_turns(self.call_id, turns)
        return reply, audio

    async def finish(self, reason: str | None = None) -> dict[str, Any]:
        return await self.api.update_call(
            self.call_id,
            {
                "status": "completed",
                "end_reason": reason or self.voice.end_reason or "completed",
                "ended_at": datetime.now(UTC).isoformat(),
                "variables": self.voice.variables,
            },
        )

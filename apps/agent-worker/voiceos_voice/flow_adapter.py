"""LiveKit LLM adapter that resolves configured intents before cloud LLM."""

import json
from typing import Any
from uuid import uuid4

from livekit.agents import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, llm
from livekit.agents.llm import ChatContext, ChoiceDelta, FunctionToolCall

from .flow import FlowEngine, match_intent


class _FlowStream(llm.LLMStream):
    def __init__(self, owner: "HybridFlowLLM", text: str, end_call: bool, **kwargs: Any) -> None:
        super().__init__(owner, **kwargs)
        self._text = text
        self._end_call = end_call

    async def _run(self) -> None:
        call = []
        if self._end_call:
            call = [
                FunctionToolCall(
                    name="end_call",
                    arguments=json.dumps({"reason": "flow_complete", "farewell": self._text}),
                    call_id=f"flow_{uuid4().hex}",
                )
            ]
        self._event_ch.send_nowait(
            llm.ChatChunk(
                id=f"flow_{uuid4().hex}",
                delta=ChoiceDelta(content=None if call else self._text, tool_calls=call),
            )
        )


class HybridFlowLLM(llm.LLM):
    """Use the local process for known intents and delegate unknown turns."""

    def __init__(self, delegate: llm.LLM, process: dict[str, Any]) -> None:
        super().__init__()
        self.delegate = delegate
        self.engine = FlowEngine(process)

    @property
    def model(self) -> str:
        return f"hybrid:{self.delegate.model}"

    @property
    def provider(self) -> str:
        return "voiceos-flow"

    def chat(self, *, chat_ctx: ChatContext, tools: list[llm.Tool] | None = None, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS, parallel_tool_calls: Any = NOT_GIVEN, tool_choice: Any = NOT_GIVEN, extra_kwargs: Any = NOT_GIVEN) -> llm.LLMStream:
        messages = chat_ctx.messages()
        text = ""
        for message in reversed(messages):
            if message.role == "user":
                text = " ".join(str(item) for item in message.content)
                break
        intent = match_intent(self.engine.config, text)
        if intent is None:
            return self.delegate.chat(
                chat_ctx=chat_ctx,
                tools=tools,
                conn_options=conn_options,
                parallel_tool_calls=parallel_tool_calls,
                tool_choice=tool_choice,
                extra_kwargs=extra_kwargs,
            )
        result = self.engine.handle(intent)
        return _FlowStream(
            self,
            result.response or "",
            result.terminal,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )

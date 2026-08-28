import asyncio

from livekit.agents import ChatContext, llm

from voiceos_voice.flow_adapter import HybridFlowLLM


class DelegateLLM(llm.LLM):
    @property
    def model(self) -> str:
        return "test-model"

    @property
    def provider(self) -> str:
        return "test"

    def chat(self, **_: object) -> llm.LLMStream:
        raise AssertionError("delegate should not be called for a configured intent")


def test_hybrid_flow_resolves_known_intent_without_delegate() -> None:
    async def run() -> None:
        adapter = HybridFlowLLM(
            DelegateLLM(),
            {
                "states": [
                    {
                        "id": "start",
                        "prompt": "Tudo certo?",
                        "transitions": [{"intent": "yes", "next": "done"}],
                    },
                    {"id": "done", "prompt": "Confirmado."},
                ],
                "intents": [{"id": "yes", "examples": ["sim"]}],
            },
        )
        ctx = ChatContext()
        ctx.add_message(role="user", content="sim")
        stream = adapter.chat(chat_ctx=ctx, tools=[])
        chunks = [chunk async for chunk in stream]
        assert chunks[0].delta is not None
        assert chunks[0].delta.content == "Confirmado."
        await stream.aclose()

    asyncio.run(run())

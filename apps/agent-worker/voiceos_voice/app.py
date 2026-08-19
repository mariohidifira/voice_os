from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .contracts import LLMResponse
from .prompting import build_system_prompt
from .providers import MockLLM, MockRAG, MockTTS
from .session import VoiceSession
from .tools import ToolRegistry


@dataclass
class WorkerState:
    active_rooms: int = 0
    draining: bool = False


class SimulationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    reply: str = Field(default="Como posso ajudar?", min_length=1, max_length=4000)
    knowledge: list[str] = Field(default_factory=list, max_length=5)


class SimulationResponse(BaseModel):
    text: str
    audio_chunks: int
    metrics: dict[str, int]


state = WorkerState()
app = FastAPI(title="VoiceOS agent worker", version="0.1.0")


@app.get("/health")
async def healthcheck() -> dict[str, object]:
    return {
        "status": "draining" if state.draining else "ok",
        "service": "agent-worker",
        "active_rooms": state.active_rooms,
        "draining": state.draining,
    }


@app.post("/v1/simulations", response_model=SimulationResponse)
async def simulate(request: SimulationRequest) -> SimulationResponse:
    if state.draining:
        raise HTTPException(status_code=503, detail="worker is draining")
    state.active_rooms += 1
    try:
        system_prompt = build_system_prompt(
            {"name": "local"},
            {"name": "mock", "system_prompt": "Atenda o usuário em português."},
            channel="simulation",
            variables={},
            end_user=None,
            tools=[],
            now=datetime.now(UTC),
        )
        session = VoiceSession(
            MockLLM([LLMResponse(text=request.reply)]),
            MockLLM(),
            MockTTS(),
            MockTTS(),
            ToolRegistry(),
            system_prompt,
            rag=MockRAG(request.knowledge),
        )
        text, audio = await session.turn(request.text)
        return SimulationResponse(
            text=text,
            audio_chunks=len(audio),
            metrics=asdict(session.metrics),
        )
    finally:
        state.active_rooms -= 1

import httpx
import pytest
from voiceos_voice.app import app, state


@pytest.mark.asyncio
async def test_simulation_runs_complete_mock_pipeline() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.post(
            "/v1/simulations",
            json={"text": "Quando abre?", "reply": "Abrimos às nove.", "knowledge": ["Horário: 9h"]},
        )
    assert response.status_code == 200
    assert response.json() == {
        "text": "Abrimos às nove.",
        "audio_chunks": 1,
        "metrics": {
            "turns": 1,
            "barge_ins": 0,
            "llm_fallbacks": 0,
            "tts_fallbacks": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "rag_queries": 1,
        },
    }
    assert state.active_rooms == 0


@pytest.mark.asyncio
async def test_simulation_rejects_new_room_while_draining() -> None:
    state.draining = True
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
            response = await client.post("/v1/simulations", json={"text": "Olá"})
        assert response.status_code == 503
    finally:
        state.draining = False

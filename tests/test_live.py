import json
from uuid import UUID

from voiceos_api.live import channel_name, encode_sse


def test_tenant_scoped_channel_and_sse_encoding() -> None:
    tenant_id = UUID(int=1)
    call_id = UUID(int=2)
    assert channel_name(tenant_id, call_id) == f"tenant:{tenant_id}:call:{call_id}"
    encoded = encode_sse({"type": "turn.user", "text": "Olá"})
    assert encoded.startswith("event: turn.user\ndata: ")
    assert json.loads(encoded.split("data: ", 1)[1]) == {"type": "turn.user", "text": "Olá"}

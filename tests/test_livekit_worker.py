import pytest
from voiceos_voice.livekit_worker import room_metadata


def test_room_metadata_parses_dispatch_contract() -> None:
    assert room_metadata('{"agent_id":"abc","channel":"web","variables":{"lead":"42"}}') == {
        "agent_id": "abc",
        "channel": "web",
        "variables": {"lead": "42"},
    }


@pytest.mark.parametrize("raw", ["[]", "not-json"])
def test_room_metadata_rejects_invalid_dispatch_contract(raw: str) -> None:
    with pytest.raises(ValueError, match="metadata"):
        room_metadata(raw)

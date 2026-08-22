import json
from uuid import uuid4

import jwt
import pytest
from voiceos_api.config import Settings
from voiceos_api.livekit_sessions import LiveKitSessions


@pytest.mark.asyncio
async def test_dev_session_token_contains_room_and_publish_grants() -> None:
    settings = Settings(livekit_url="wss://example.invalid", livekit_api_key="dev-key", livekit_api_secret="dev-secret")
    call_id, agent_id = uuid4(), uuid4()
    result = await LiveKitSessions(settings).provision(
        call_id=call_id,
        agent_id=agent_id,
        version="draft",
        variables={"customer": "42"},
        end_user={"name": "Mario"},
    )
    claims = jwt.decode(result["token"], "dev-secret", algorithms=["HS256"], audience=None, options={"verify_aud": False})
    assert result["room_name"] == f"voiceos_{call_id}"
    assert claims["video"]["room"] == result["room_name"]
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True
    assert claims["video"]["canSubscribe"] is True
    assert json.loads(claims["metadata"])["call_id"] == str(call_id)

import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from livekit import api as livekit_api

from .config import Settings, get_settings


class LiveKitSessions:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def provision(
        self,
        *,
        call_id: UUID,
        agent_id: UUID,
        version: str,
        variables: dict[str, Any],
        end_user: dict[str, Any] | None,
    ) -> dict[str, str]:
        room_name = f"voiceos_{call_id}"
        metadata = json.dumps(
            {
                "call_id": str(call_id),
                "agent_id": str(agent_id),
                "version": version,
                "variables": variables,
                "end_user": end_user or {},
            },
            separators=(",", ":"),
        )
        if not self.settings.livekit_url.endswith(".invalid"):
            client = livekit_api.LiveKitAPI(
                url=self.settings.livekit_url,
                api_key=self.settings.livekit_api_key,
                api_secret=self.settings.livekit_api_secret,
            )
            try:
                await client.room.create_room(
                    livekit_api.CreateRoomRequest(name=room_name, metadata=metadata, empty_timeout=60)
                )
            finally:
                await client.aclose()
        identity = f"web_{uuid4().hex}"
        token = (
            livekit_api.AccessToken(self.settings.livekit_api_key, self.settings.livekit_api_secret)
            .with_identity(identity)
            .with_name("VoiceOS Web")
            .with_metadata(json.dumps({"call_id": str(call_id)}, separators=(",", ":")))
            .with_ttl(timedelta(hours=1))
            .with_grants(
                livekit_api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .to_jwt()
        )
        return {"room_name": room_name, "token": token}


def get_livekit_sessions() -> LiveKitSessions:
    return LiveKitSessions(get_settings())

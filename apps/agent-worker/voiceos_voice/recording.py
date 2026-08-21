import os
from typing import Protocol
from uuid import UUID

from livekit import api


class EgressStarter(Protocol):
    async def start_room_composite_egress(
        self, request: api.RoomCompositeEgressRequest
    ) -> api.EgressInfo: ...


async def start_egress(
    egress: EgressStarter,
    *,
    room_name: str,
    tenant_id: UUID,
    call_id: UUID,
    bucket: str,
    region: str,
) -> tuple[str, str]:
    key = f"recordings/{tenant_id}/{call_id}.ogg"
    request = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG,
                filepath=key,
                s3=api.S3Upload(
                    bucket=bucket,
                    region=region,
                    access_key=os.getenv("AWS_ACCESS_KEY_ID", ""),
                    secret=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                ),
            )
        ],
    )
    info = await egress.start_room_composite_egress(request)
    return info.egress_id, key


async def start_room_recording(
    *, room_name: str, tenant_id: UUID, call_id: UUID, bucket: str, region: str
) -> tuple[str, str]:
    async with api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    ) as client:
        return await start_egress(
            client.egress,
            room_name=room_name,
            tenant_id=tenant_id,
            call_id=call_id,
            bucket=bucket,
            region=region,
        )

from typing import Any
from uuid import uuid4

import pytest
from livekit import api
from voiceos_api.repository import MemoryRepository
from voiceos_api.routes import _egress_recording
from voiceos_api.store import MemoryStore
from voiceos_voice.recording import start_egress


@pytest.mark.asyncio
async def test_start_egress_uses_audio_only_ogg_and_tenant_scoped_s3_key() -> None:
    captured: list[api.RoomCompositeEgressRequest] = []

    class Egress:
        async def start_room_composite_egress(
            self, request: api.RoomCompositeEgressRequest
        ) -> Any:
            captured.append(request)
            return type("Info", (), {"egress_id": "EG_123"})()

    tenant_id, call_id = uuid4(), uuid4()
    egress_id, key = await start_egress(
        Egress(),
        room_name="room-42",
        tenant_id=tenant_id,
        call_id=call_id,
        bucket="recordings",
        region="sa-east-1",
    )
    request = captured[0]
    assert egress_id == "EG_123"
    assert key == f"recordings/{tenant_id}/{call_id}.ogg"
    assert request.audio_only is True and request.layout == ""
    assert request.file_outputs[0].file_type == api.EncodedFileType.OGG
    assert request.file_outputs[0].filepath == key
    assert request.file_outputs[0].s3.bucket == "recordings"


def test_egress_webhook_maps_completed_file_to_recording() -> None:
    call_id = uuid4()
    event = api.WebhookEvent(
        event="egress_ended",
        egress_info=api.EgressInfo(
            egress_id="EG_123",
            file_results=[
                api.FileInfo(
                    filename=f"recordings/tenant/{call_id}.ogg",
                    location=f"s3://recordings/recordings/tenant/{call_id}.ogg",
                    duration=12_400_000_000,
                    size=4096,
                )
            ],
        ),
    )
    mapped = _egress_recording(event)
    assert mapped is not None
    mapped_call_id, recording = mapped
    assert mapped_call_id == call_id
    assert recording["status"] == "ready"
    assert recording["duration_s"] == 12
    assert recording["size_bytes"] == 4096


@pytest.mark.asyncio
async def test_memory_repository_upserts_recording_into_call_detail() -> None:
    memory = MemoryStore()
    repository = MemoryRepository(memory)
    tenant_id, agent_id = uuid4(), uuid4()
    call = await repository.create_internal_call(
        {"tenant_id": tenant_id, "agent_id": agent_id, "agent_version_id": None, "channel": "web", "livekit_room": "room", "variables": {}, "metadata": {}}
    )
    await repository.upsert_call_recording(
        call["id"], {"s3_key": f"recordings/{tenant_id}/{call['id']}.ogg", "format": "ogg", "status": "ready"}
    )
    detail = await repository.get_call_detail(tenant_id, call["id"])
    assert detail is not None
    assert detail["recording"]["status"] == "ready"

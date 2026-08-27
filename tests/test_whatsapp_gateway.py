from voiceos_api.config import Settings
from voiceos_api.whatsapp import WhatsAppGateway


async def test_whatsapp_gateway_uses_local_stub_for_dev_tokens() -> None:
    gateway = WhatsAppGateway(
        Settings(app_env="dev"),
        "token-local-dev-123",
        "phone-123",
    )

    text_id = await gateway.send_text("+5511999999999", "Olá")
    audio_id = await gateway.send_audio("+5511999999999", "media-123")
    audio_bytes_id = await gateway.send_audio_bytes(
        "+5511999999999",
        b"audio",
        filename="reply.ogg",
        content_type="audio/ogg",
    )
    media = await gateway.download_media("media-xyz")

    assert text_id.startswith("wamid.stub.")
    assert audio_id.startswith("wamid.stub.")
    assert audio_bytes_id.startswith("wamid.stub.")
    assert media == b"stub-media:media-xyz"

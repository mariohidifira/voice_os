import pytest
from voiceos_api.config import Settings
from voiceos_api.secrets import EnvelopeCipher


@pytest.mark.asyncio
async def test_local_envelope_cipher_roundtrip() -> None:
    cipher = EnvelopeCipher(Settings(app_env="test", auth_secret="x" * 32))
    encrypted, key_id = await cipher.encrypt("sensitive")
    assert encrypted != b"sensitive"
    assert await cipher.decrypt(encrypted, key_id) == "sensitive"

import sys
import types

import pytest
from voiceos_api.config import Settings
from voiceos_api.secrets import EnvelopeCipher


@pytest.mark.asyncio
async def test_local_envelope_cipher_roundtrip() -> None:
    cipher = EnvelopeCipher(Settings(app_env="test", auth_secret="x" * 32))
    encrypted, key_id = await cipher.encrypt("sensitive")
    assert encrypted != b"sensitive"
    assert await cipher.decrypt(encrypted, key_id) == "sensitive"


@pytest.mark.asyncio
async def test_kms_envelope_cipher_uses_encrypt_and_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeKMS:
        def encrypt(self, **kwargs: object) -> dict[str, bytes]:
            assert kwargs["Plaintext"] == b"sensitive"
            return {"CiphertextBlob": b"ciphertext"}

        def decrypt(self, **kwargs: object) -> dict[str, bytes]:
            assert kwargs["CiphertextBlob"] == b"ciphertext"
            return {"Plaintext": b"sensitive"}

    fake_boto3 = types.SimpleNamespace(client=lambda *_args, **_kwargs: FakeKMS())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    settings = Settings(app_env="prod", aws_kms_key_id="arn:kms:test", aws_region="sa-east-1")
    cipher = EnvelopeCipher(settings)
    encrypted, key_id = await cipher.encrypt("sensitive")
    assert encrypted == b"ciphertext" and key_id == settings.aws_kms_key_id
    assert await cipher.decrypt(encrypted, key_id) == "sensitive"

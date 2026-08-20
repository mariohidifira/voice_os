import asyncio
import hashlib
import importlib
import os
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import Settings, get_settings


class SecretCipher(Protocol):
    async def encrypt(self, plaintext: str) -> tuple[bytes, str]: ...

    async def decrypt(self, ciphertext: bytes, key_id: str) -> str: ...


class EnvelopeCipher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def encrypt(self, plaintext: str) -> tuple[bytes, str]:
        if self.settings.aws_kms_key_id:
            boto3 = importlib.import_module("boto3")
            kms = boto3.client("kms", region_name=self.settings.aws_region)
            response = await asyncio.to_thread(kms.encrypt, KeyId=self.settings.aws_kms_key_id, Plaintext=plaintext.encode(), EncryptionContext={"service": "voiceos"})
            return response["CiphertextBlob"], self.settings.aws_kms_key_id
        if self.settings.app_env not in {"dev", "test"}:
            raise RuntimeError("AWS_KMS_KEY_ID is required outside dev/test")
        key = hashlib.sha256(self.settings.auth_secret.encode()).digest()
        nonce = os.urandom(12)
        return nonce + AESGCM(key).encrypt(nonce, plaintext.encode(), b"voiceos-secret"), "local-aesgcm-v1"

    async def decrypt(self, ciphertext: bytes, key_id: str) -> str:
        if key_id != "local-aesgcm-v1":
            boto3 = importlib.import_module("boto3")
            kms = boto3.client("kms", region_name=self.settings.aws_region)
            response = await asyncio.to_thread(kms.decrypt, CiphertextBlob=ciphertext, EncryptionContext={"service": "voiceos"})
            plaintext = response["Plaintext"]
            if not isinstance(plaintext, bytes):
                raise TypeError("KMS returned invalid plaintext")
            return plaintext.decode()
        key = hashlib.sha256(self.settings.auth_secret.encode()).digest()
        return AESGCM(key).decrypt(ciphertext[:12], ciphertext[12:], b"voiceos-secret").decode()


def get_secret_cipher() -> SecretCipher:
    return EnvelopeCipher(get_settings())

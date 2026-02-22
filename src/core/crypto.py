import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.core.config import get_settings

_NONCE_SIZE = 12  # 96-bit nonce — standard recommendation for AES-GCM


def _get_key() -> bytes:
    return bytes.fromhex(get_settings().ENCRYPTION_KEY)


def encrypt(plaintext: str) -> str:
    """AES-256-GCM encrypt. Returns URL-safe base64(nonce || ciphertext+tag)."""
    key = _get_key()
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(encrypted: str) -> str:
    """AES-256-GCM decrypt. Raises InvalidTag on any tampering."""
    key = _get_key()
    raw = base64.urlsafe_b64decode(encrypted)
    nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode()

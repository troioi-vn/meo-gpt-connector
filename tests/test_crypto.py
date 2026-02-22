import base64
from unittest.mock import patch

import pytest
from cryptography.exceptions import InvalidTag

from tests.conftest import TEST_SETTINGS


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("src.core.crypto.get_settings", return_value=TEST_SETTINGS):
        yield


def test_round_trip():
    from src.core.crypto import decrypt, encrypt

    token = "sanctum|abc123xyz"
    assert decrypt(encrypt(token)) == token


def test_unique_ciphertext_per_call():
    """Each call must produce a unique ciphertext — different random nonce."""
    from src.core.crypto import encrypt

    token = "same-token"
    assert encrypt(token) != encrypt(token)


def test_tampered_ciphertext_raises():
    """Any bit-flip in the ciphertext must raise (GCM authentication tag check)."""
    from src.core.crypto import decrypt, encrypt

    encrypted = encrypt("sensitive")
    raw = bytearray(base64.urlsafe_b64decode(encrypted))
    raw[20] ^= 0xFF  # flip a byte in the ciphertext body
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode()

    with pytest.raises(InvalidTag):
        decrypt(tampered)


def test_tampered_tag_raises():
    """Flipping a byte in the GCM tag itself must also raise."""
    from src.core.crypto import decrypt, encrypt

    encrypted = encrypt("sensitive")
    raw = bytearray(base64.urlsafe_b64decode(encrypted))
    raw[-1] ^= 0xFF  # flip the last byte (inside the 16-byte auth tag)
    tampered = base64.urlsafe_b64encode(bytes(raw)).decode()

    with pytest.raises(InvalidTag):
        decrypt(tampered)

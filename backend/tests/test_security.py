"""
Tests for AES-256-GCM encryption / decryption.

Uses the test encryption key set in conftest.py — never real secrets.
"""

import base64
import os

import pytest


@pytest.fixture(autouse=True)
def _set_test_encryption_key(monkeypatch):
    """Ensure a valid 32-byte key is available for every test."""
    test_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("FORGE_ENCRYPTION_KEY", test_key)
    # Force the settings singleton to reload the value
    from app.config import settings
    object.__setattr__(settings, "FORGE_ENCRYPTION_KEY", test_key)


def test_encrypt_decrypt_roundtrip():
    """encrypt → decrypt must return the original plaintext."""
    from app.core.security import decrypt_api_key, encrypt_api_key

    original = "sk-ant-api03-secret-key-value"
    encrypted, iv, tag = encrypt_api_key(original)

    assert isinstance(encrypted, bytes)
    assert isinstance(iv, bytes)
    assert len(iv) == 12  # GCM nonce
    assert isinstance(tag, bytes)
    assert len(tag) == 16  # GCM auth tag

    decrypted = decrypt_api_key(encrypted, iv, tag)
    assert decrypted == original


def test_unique_iv_per_encryption():
    """Each encryption call must produce a different IV (nonce reuse = catastrophic)."""
    from app.core.security import encrypt_api_key

    _, iv1, _ = encrypt_api_key("key-1")
    _, iv2, _ = encrypt_api_key("key-2")
    assert iv1 != iv2


def test_decrypt_with_wrong_iv_fails():
    """Decryption with wrong IV must raise an error."""
    from app.core.security import decrypt_api_key, encrypt_api_key

    encrypted, _iv, tag = encrypt_api_key("my-secret")
    wrong_iv = os.urandom(12)

    with pytest.raises(Exception):
        decrypt_api_key(encrypted, wrong_iv, tag)


def test_decrypt_with_tampered_ciphertext_fails():
    """Tampered ciphertext must fail GCM authentication."""
    from app.core.security import decrypt_api_key, encrypt_api_key

    encrypted, iv, tag = encrypt_api_key("my-secret")
    tampered = bytearray(encrypted)
    tampered[0] ^= 0xFF  # Flip one byte

    with pytest.raises(Exception):
        decrypt_api_key(bytes(tampered), iv, tag)


def test_invalid_key_length_raises():
    """A key that doesn't decode to 32 bytes must raise ValueError."""
    from app.config import settings
    from app.core.security import encrypt_api_key

    # Set a 16-byte key (too short)
    short_key = base64.b64encode(os.urandom(16)).decode()
    object.__setattr__(settings, "FORGE_ENCRYPTION_KEY", short_key)

    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_api_key("test")

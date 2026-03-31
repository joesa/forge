"""
AES-256-GCM encryption for user API keys.

Architecture rule #3: IV stored separately from ciphertext.
A fresh random 12-byte IV is generated for every encryption call.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _get_key() -> bytes:
    """Decode the base64-encoded 32-byte encryption key from config."""
    raw = base64.b64decode(settings.FORGE_ENCRYPTION_KEY)
    if len(raw) != 32:
        raise ValueError(
            "FORGE_ENCRYPTION_KEY must decode to exactly 32 bytes "
            f"(got {len(raw)})"
        )
    return raw


def encrypt_api_key(key: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt a plaintext API key with AES-256-GCM.

    Returns
    -------
    (ciphertext_with_tag, iv, tag)
        • ciphertext_with_tag  – encrypted data **including** the 16-byte GCM tag
        • iv                   – the 12-byte nonce used for this encryption
        • tag                  – the last 16 bytes of ciphertext_with_tag (for
          callers that store it separately)
    """
    encryption_key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(encryption_key)
    ciphertext_with_tag = aesgcm.encrypt(iv, key.encode("utf-8"), None)

    # GCM appends a 16-byte authentication tag
    tag = ciphertext_with_tag[-16:]

    return ciphertext_with_tag, iv, tag


def decrypt_api_key(encrypted: bytes, iv: bytes, tag: bytes) -> str:
    """
    Decrypt an AES-256-GCM encrypted API key.

    Parameters
    ----------
    encrypted : bytes
        The full ciphertext **including** the GCM tag (as returned by
        ``encrypt_api_key``).  If the caller stored ciphertext and tag
        separately, concatenate them before passing here.
    iv : bytes
        The 12-byte nonce used during encryption.
    tag : bytes
        Kept for interface symmetry — the tag is already embedded in
        *encrypted*.  If you stored them separately, pass
        ``ciphertext + tag`` as *encrypted*.
    """
    encryption_key = _get_key()
    aesgcm = AESGCM(encryption_key)
    plaintext = aesgcm.decrypt(iv, encrypted, None)
    return plaintext.decode("utf-8")

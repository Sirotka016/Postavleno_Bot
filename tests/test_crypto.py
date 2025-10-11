from __future__ import annotations

from postavleno_bot.core.crypto import decrypt_str, encrypt_str


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "super-secret-token"
    encrypted = encrypt_str(plain)
    assert isinstance(encrypted, bytes)
    assert decrypt_str(encrypted) == plain

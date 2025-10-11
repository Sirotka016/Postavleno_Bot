from __future__ import annotations

from postavleno_bot.core.crypto import decrypt_json, decrypt_str, encrypt_json, encrypt_str


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "super-secret-token"
    encrypted = encrypt_str(plain)
    assert isinstance(encrypted, bytes)
    assert decrypt_str(encrypted) == plain


def test_encrypt_decrypt_json() -> None:
    payload = {"value": "secret", "count": 5}
    encrypted = encrypt_json(payload)
    assert isinstance(encrypted, bytes)
    decrypted = decrypt_json(encrypted)
    assert decrypted == payload

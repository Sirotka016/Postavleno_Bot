from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings
from .logging import get_logger


class SecretKeyError(RuntimeError):
    """Raised when SECRET_KEY is missing or invalid."""


@lru_cache
def _get_fernet() -> Fernet:
    settings = get_settings()
    secret_value = settings.secret_key.get_secret_value()
    if not secret_value:
        logger = get_logger(__name__).bind(action="crypto.init")
        logger.error("SECRET_KEY не задан", outcome="fail")
        raise SecretKeyError("SECRET_KEY is required")
    try:
        key_bytes = secret_value.encode()
        return Fernet(key_bytes)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger = get_logger(__name__).bind(action="crypto.init")
        logger.error("Не удалось инициализировать шифрование", error=str(exc), outcome="fail")
        raise SecretKeyError("Invalid SECRET_KEY") from exc


def encrypt_bytes(data: bytes) -> bytes:
    fernet = _get_fernet()
    return fernet.encrypt(data)


def decrypt_bytes(blob: bytes) -> bytes:
    fernet = _get_fernet()
    try:
        return fernet.decrypt(blob)
    except InvalidToken as exc:  # pragma: no cover - defensive branch
        logger = get_logger(__name__).bind(action="crypto.decrypt")
        logger.error("Ошибка расшифровки", outcome="fail")
        raise SecretKeyError("Failed to decrypt data") from exc


def decrypt_str(blob: bytes) -> str:
    return decrypt_bytes(blob).decode("utf-8")


def encrypt_str(text: str) -> bytes:
    return encrypt_bytes(text.encode("utf-8"))


def encrypt_json(data: Any) -> bytes:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return encrypt_bytes(payload)


def decrypt_json(blob: bytes) -> Any:
    plaintext = decrypt_bytes(blob).decode("utf-8")
    return json.loads(plaintext)

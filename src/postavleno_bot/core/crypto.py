from __future__ import annotations

from functools import lru_cache

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


def encrypt_str(text: str) -> bytes:
    fernet = _get_fernet()
    token: bytes = fernet.encrypt(text.encode("utf-8"))
    return token


def decrypt_str(blob: bytes) -> str:
    fernet = _get_fernet()
    try:
        decrypted_bytes: bytes = fernet.decrypt(blob)
    except InvalidToken as exc:  # pragma: no cover - defensive branch
        logger = get_logger(__name__).bind(action="crypto.decrypt")
        logger.error("Ошибка расшифровки токена", outcome="fail")
        raise SecretKeyError("Failed to decrypt data") from exc
    return decrypted_bytes.decode("utf-8")

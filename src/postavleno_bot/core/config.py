from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    bot_token: SecretStr = Field(
        ...,
        description="Токен Telegram-бота",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TG_BOT_TOKEN"),
    )
    database_url: str = Field(
        "sqlite+aiosqlite:///./data/app.db",
        description="URL подключения к базе данных",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    secret_key: SecretStr = Field(
        ...,
        description="Секретный ключ для шифрования токенов",
        validation_alias=AliasChoices("SECRET_KEY", "FERNET_SECRET_KEY"),
    )
    log_level: str = Field("INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    log_json: bool = Field(True, validation_alias=AliasChoices("LOG_JSON"))
    log_rich: bool = Field(True, validation_alias=AliasChoices("LOG_RICH"))
    sentry_dsn: str | None = Field(None, validation_alias=AliasChoices("SENTRY_DSN"))
    http_timeout_s: float = Field(30.0, validation_alias=AliasChoices("HTTP_TIMEOUT_S"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of :class:`Settings`."""

    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:  # pragma: no cover - defensive branch
        missing = "TELEGRAM_BOT_TOKEN (или BOT_TOKEN/TG_BOT_TOKEN)"
        message = f"Не найден обязательный токен бота. Укажите {missing} в .env. Подробности: {exc}"
        raise RuntimeError(message) from exc

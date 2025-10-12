from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    bot_token: SecretStr = Field(
        ...,
        description="Токен Telegram-бота",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TG_BOT_TOKEN"),
    )
    accounts_dir: Path = Field(
        Path("data/accounts"),
        description="Каталог для хранения данных аккаунтов",
        validation_alias=AliasChoices("ACCOUNTS_DIR", "POSTAVLENO_ACCOUNTS_DIR"),
    )
    delete_user_messages: bool = Field(
        True,
        description="Удалять ли пользовательские сообщения после обработки",
        validation_alias=AliasChoices("DELETE_USER_MESSAGES"),
    )
    log_level: str = Field("INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    log_json: bool = Field(True, validation_alias=AliasChoices("LOG_JSON"))
    log_rich: bool = Field(True, validation_alias=AliasChoices("LOG_RICH"))
    http_timeout_s: float = Field(30.0, validation_alias=AliasChoices("HTTP_TIMEOUT_S"))

    smtp_host: str = Field(
        "smtp.gmail.com",
        description="SMTP сервер для исходящих писем",
        validation_alias=AliasChoices("SMTP_HOST"),
    )
    smtp_port: int = Field(587, description="SMTP порт", validation_alias=AliasChoices("SMTP_PORT"))
    smtp_user: str = Field(
        "NeAniiime@gmail.com",
        description="Учётная запись для отправки писем",
        validation_alias=AliasChoices("SMTP_USER"),
    )
    smtp_password: SecretStr = Field(
        SecretStr(""),
        description="Пароль приложения для SMTP",
        validation_alias=AliasChoices("SMTP_PASSWORD"),
    )
    smtp_sender: str = Field(
        "Postavleno_Bot",
        description="Имя отправителя в письмах",
        validation_alias=AliasChoices("SMTP_SENDER"),
    )
    cache_ttl_seconds: int = Field(
        60,
        description="TTL кэша для обращений к внешним API",
        validation_alias=AliasChoices("CACHE_TTL_SECONDS"),
    )

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
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as exc:  # pragma: no cover - defensive branch
        missing = "TELEGRAM_BOT_TOKEN (или BOT_TOKEN/TG_BOT_TOKEN)"
        message = f"Не найден обязательный токен бота. Укажите {missing} в .env. Подробности: {exc}"
        raise RuntimeError(message) from exc
    settings.accounts_dir.mkdir(parents=True, exist_ok=True)
    return settings

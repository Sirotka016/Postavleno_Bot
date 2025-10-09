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
    wb_api_token: SecretStr | None = Field(
        None,
        description="Токен Wildberries API",
        validation_alias=AliasChoices("WB_API_TOKEN", "WILDBERRIES_API_TOKEN"),
    )
    log_level: str = Field("INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    log_json: bool = Field(True, validation_alias=AliasChoices("LOG_JSON"))
    log_rich: bool = Field(True, validation_alias=AliasChoices("LOG_RICH"))
    sentry_dsn: str | None = Field(None, validation_alias=AliasChoices("SENTRY_DSN"))
    local_store_name: str = Field(
        "FootballShop",
        validation_alias=AliasChoices("LOCAL_STORE_NAME"),
        description="Название локального склада для итоговой выгрузки",
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
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:  # pragma: no cover - defensive branch
        missing = "TELEGRAM_BOT_TOKEN (или BOT_TOKEN/TG_BOT_TOKEN)"
        message = f"Не найден обязательный токен бота. Укажите {missing} в .env. Подробности: {exc}"
        raise RuntimeError(message) from exc

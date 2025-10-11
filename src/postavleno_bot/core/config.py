from __future__ import annotations

from functools import lru_cache
from typing import Literal

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
    moysklad_auth_mode: Literal["basic", "token"] = Field(
        "token",
        validation_alias=AliasChoices("MOYSKLAD_AUTH_MODE"),
        description="Режим аутентификации в API МойСклад",
    )
    moysklad_login: str | None = Field(
        None,
        validation_alias=AliasChoices("MOYSKLAD_LOGIN"),
        description="Логин пользователя МойСклад для basic-аутентификации",
    )
    moysklad_password: str | None = Field(
        None,
        validation_alias=AliasChoices("MOYSKLAD_PASSWORD"),
        description="Пароль пользователя МойСклад для basic-аутентификации",
    )
    moysklad_token: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("MOYSKLAD_TOKEN"),
        description="API-токен МойСклад для bearer-аутентификации",
    )
    moysklad_page_size: int = Field(
        1000,
        validation_alias=AliasChoices("MOYSKLAD_PAGE_SIZE"),
        description="Количество строк, загружаемых за один запрос к /report/stock/all",
    )
    moysklad_quantity_field: Literal["quantity", "stock"] = Field(
        "quantity",
        validation_alias=AliasChoices("MOYSKLAD_QUANTITY_FIELD"),
        description="Какое поле использовать из ответов МойСклад при подсчёте остатков",
    )
    local_store_name: str = Field(
        "FootballShop",
        validation_alias=AliasChoices("LOCAL_STORE_NAME", "BRAND_STORE_NAME"),
        description='Значение колонки "Склад" для итоговой выгрузки',
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

from __future__ import annotations

from datetime import datetime

from aiogram.exceptions import TelegramBadRequest

from postavleno_bot.handlers import menu
from postavleno_bot.utils.safe_telegram import _is_not_modified_error


def test_main_card_text_contains_expected_phrases() -> None:
    now = datetime(2024, 7, 1, 12, 30)
    text = menu.build_greeting_text(now=now)
    assert "Привет!" in text
    assert "Postavleno_Bot" in text
    assert "ℹ️ Помощь" in text
    assert "Обновлено: 01.07.2024 12:30" in text


def test_help_card_text_contains_expected_phrases() -> None:
    now = datetime(2024, 7, 1, 9, 15)
    text = menu.build_help_text(now=now)
    assert "ℹ️ Помощь" in text
    assert "🔎 Статус заказа" in text
    assert "📦 Товары" in text
    assert "Обновлено: 01.07.2024 09:15" in text


def test_status_card_text_mentions_future_features() -> None:
    now = datetime(2024, 7, 2, 18, 5)
    text = menu.build_status_text(now=now)
    assert "Совсем скоро" in text
    assert "🔄 Обновить" in text
    assert "Обновлено: 02.07.2024 18:05" in text


def test_products_card_text_mentions_catalog() -> None:
    now = datetime(2024, 7, 3, 8, 45)
    text = menu.build_products_text(now=now)
    assert "каталог" in text.lower()
    assert "Обновлено: 03.07.2024 08:45" in text


def test_is_not_modified_error_detection() -> None:
    error = TelegramBadRequest("Bad Request: message is not modified")
    assert _is_not_modified_error(error) is True


def test_is_not_modified_error_detection_false() -> None:
    error = TelegramBadRequest("Bad Request: chat not found")
    assert _is_not_modified_error(error) is False

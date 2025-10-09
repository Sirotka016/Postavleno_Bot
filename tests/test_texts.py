from __future__ import annotations

from datetime import datetime

from postavleno_bot.handlers import menu
from postavleno_bot.utils.safe_telegram import is_not_modified_error


def test_greeting_text_contains_expected_phrases() -> None:
    now = datetime(2024, 7, 1, 12, 30)
    text = menu.build_greeting_text(now=now)
    assert "Привет!" in text
    assert "Postavleno_Bot" in text
    assert "Используйте кнопки" in text
    assert "Обновлено: 01.07.2024 12:30" in text


def test_is_not_modified_error_detection() -> None:
    assert is_not_modified_error("Bad Request: message is not modified") is True


def test_is_not_modified_error_detection_false() -> None:
    assert is_not_modified_error("Bad Request: chat not found") is False

from __future__ import annotations

from postavleno_bot.handlers import menu


def test_main_card_text_contains_expected_phrases() -> None:
    text = menu._main_card_text()
    assert "Привет!" in text
    assert "Postavleno_Bot" in text
    assert "Обновлено:" in text


def test_help_card_text_contains_expected_phrases() -> None:
    text = menu._help_card_text()
    assert "Чем я могу помочь" in text
    assert "🔄 Обновить" in text
    assert "Обновлено:" in text


def test_status_card_text_mentions_future_features() -> None:
    text = menu._status_card_text()
    assert "Совсем скоро" in text
    assert "Обновлено:" in text


def test_products_card_text_mentions_catalog() -> None:
    text = menu._products_card_text()
    assert "каталог" in text.lower()
    assert "Обновлено:" in text

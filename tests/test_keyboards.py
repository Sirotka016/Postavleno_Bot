from __future__ import annotations

from postavleno_bot.keyboards.common import main_menu


def test_main_menu_structure() -> None:
    keyboard = main_menu()
    assert keyboard.resize_keyboard is True
    assert keyboard.input_field_placeholder == "Выберите действие…"

    rows = [[button.text for button in row] for row in keyboard.keyboard]
    assert rows == [["🔎 Статус заказа", "📦 Товары"], ["ℹ️ Помощь"]]

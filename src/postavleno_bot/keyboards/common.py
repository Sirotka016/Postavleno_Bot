from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    """Reply keyboard with the main navigation buttons."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔎 Статус заказа"),
                KeyboardButton(text="📦 Товары"),
            ],
            [
                KeyboardButton(text="ℹ️ Помощь"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
        one_time_keyboard=False,
    )

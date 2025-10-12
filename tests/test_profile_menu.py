from aiogram.types import InlineKeyboardMarkup

from postavleno_bot.ui import kb_home, kb_profile


def extract_texts(markup: InlineKeyboardMarkup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def test_home_menu_order_for_authenticated_user() -> None:
    texts = extract_texts(kb_home(True))
    assert texts == [
        "👤 Профиль",
        "📊 Остатки WB (Общие)",
        "🏷️ Остатки WB (Склады)",
        "🔄 Обновить",
        "✖️ Выйти",
    ]


def test_profile_menu_structure() -> None:
    texts = extract_texts(kb_profile())
    assert texts == [
        "🏢 Компания",
        "✉️ Почта",
        "🔑 WB API",
        "🚪 Выйти из профиля",
        "🗑️ Удалить аккаунт",
        "🔄 Обновить",
        "◀️ Назад",
        "✖️ Выйти",
    ]
    assert all("Остатки" not in text for text in texts)

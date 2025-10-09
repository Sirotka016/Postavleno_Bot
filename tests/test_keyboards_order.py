from __future__ import annotations

from postavleno_bot.handlers import menu


def test_wb_all_buttons_order_with_pages() -> None:
    keyboard = menu.build_stock_results_keyboard(total_pages=5, current_page=2)
    rows = keyboard.inline_keyboard

    assert [button.text for button in rows[0]] == ["⬇️ Выгрузить"]

    page_rows = rows[1:-2]
    assert page_rows
    page_numbers = [button.text for row in page_rows for button in row]
    assert page_numbers == ["1", "2", "3", "4", "5"]

    assert [button.text for button in rows[-2]] == ["🔄 Обновить", "⬅️ Назад"]
    assert [button.text for button in rows[-1]] == ["🚪 Выйти"]


def test_store_menu_buttons_order() -> None:
    keyboard = menu.build_store_menu_keyboard()
    rows = keyboard.inline_keyboard

    assert [button.text for button in rows[0]] == ["📊 Узнать Остатки"]
    assert [button.text for button in rows[1]] == ["🔄 Обновить", "⬅️ Назад"]
    assert [button.text for button in rows[2]] == ["🚪 Выйти"]


def test_store_menu_loading_replaces_action_button() -> None:
    keyboard = menu.build_store_menu_keyboard(loading=True)
    rows = keyboard.inline_keyboard

    assert [button.text for button in rows[0]] == ["⌛ Получаю…"]
    assert [button.callback_data for button in rows[0]] == [menu.STORE_WAIT_CALLBACK]

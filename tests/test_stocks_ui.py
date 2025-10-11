from __future__ import annotations

from datetime import datetime

import pytest

from postavleno_bot.handlers import menu
from postavleno_bot.integrations.wildberries import WBAuthError, WBRatelimitError, WBStockItem
from postavleno_bot.services.stocks import (
    WarehouseSummary,
    filter_by_warehouse,
    summarize_by_warehouse,
)


def _make_item(warehouse: str, *, qty: int, nm: int = 1, article: str = "SKU") -> WBStockItem:
    return WBStockItem(
        lastChangeDate=datetime(2024, 1, 1, 12, 0),
        warehouseName=warehouse,
        supplierArticle=article,
        nmId=nm,
        barcode="b",
        quantity=qty,
        inWayToClient=0,
        inWayFromClient=0,
        quantityFull=qty,
        category=None,
        subject=None,
        brand=None,
        techSize=None,
        price=None,
        discount=None,
        scCode=None,
    )


def test_main_keyboard_has_stocks_and_store_buttons() -> None:
    keyboard = menu.build_main_keyboard()
    rows = keyboard.inline_keyboard
    assert [btn.text for btn in rows[0]] == ["📦 Остатки WB", "🏬 Остатки Склад"]
    assert [btn.text for btn in rows[1]] == ["🔄 Обновить", "🚪 Выйти"]


def test_stocks_keyboard_order_on_open() -> None:
    keyboard = menu.build_stocks_menu_keyboard()
    assert [btn.text for btn in keyboard.inline_keyboard[0]] == ["👀 Посмотреть остатки"]
    assert [btn.text for btn in keyboard.inline_keyboard[1]] == ["🔄 Обновить", "⬅️ Назад"]
    assert [btn.text for btn in keyboard.inline_keyboard[2]] == ["🚪 Выйти"]


def test_dynamic_warehouses_keyboard() -> None:
    summaries = [
        WarehouseSummary(name="Подольск", total_qty=200, sku_count=24),
        WarehouseSummary(name="Казань", total_qty=150, sku_count=12),
    ]
    keyboard, mapping = menu.build_warehouses_keyboard(summaries)

    rows = keyboard.inline_keyboard
    assert [btn.text for btn in rows[0]] == ["🧾 Все склады"]
    assert [row[0].text for row in rows[1:3]] == ["Подольск", "Казань"]
    assert [btn.text for btn in rows[-2]] == ["🔄 Обновить", "⬅️ Назад"]
    assert [btn.text for btn in rows[-1]] == ["🚪 Выйти"]

    assert set(mapping.values()) == {"Подольск", "Казань"}
    for key in mapping:
        assert key.startswith(menu.WAREHOUSE_KEY_PREFIX)


def test_summarize_by_warehouse_filters_zero_qty() -> None:
    items = [
        _make_item("Санкт-Петербург", qty=0, nm=1),
        _make_item("Подольск", qty=5, nm=2),
        _make_item("Подольск", qty=3, nm=3),
    ]
    summaries = summarize_by_warehouse(items)
    assert len(summaries) == 1
    assert summaries[0].name == "Подольск"
    assert summaries[0].total_qty == 8
    assert summaries[0].sku_count == 2


def test_filter_by_warehouse() -> None:
    items = [
        _make_item("Подольск", qty=10, nm=1),
        _make_item("Казань", qty=5, nm=2),
    ]
    podolsk_items = filter_by_warehouse(items, "Подольск")
    assert len(podolsk_items) == 1
    assert podolsk_items[0].warehouseName == "Подольск"

    all_items = filter_by_warehouse(items, None)
    assert len(all_items) == 2


@pytest.mark.parametrize(
    "error, expected_text",
    [
        (WBAuthError("fail"), "Токен WB отклонён"),
        (WBRatelimitError("rate", retry_after=12), "12 секунд"),
    ],
)
def test_error_responses_do_not_fail(error: Exception, expected_text: str) -> None:
    text, keyboard = menu._build_error_response(error)
    assert expected_text in text
    refresh_row = keyboard.inline_keyboard[0]
    assert [btn.text for btn in refresh_row] == ["🔄 Обновить", "⬅️ Назад"]

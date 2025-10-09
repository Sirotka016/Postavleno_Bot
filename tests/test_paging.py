from __future__ import annotations

from datetime import datetime

from postavleno_bot.handlers.menu import page_buttons
from postavleno_bot.integrations.wb_client import WBStockItem
from postavleno_bot.services.stocks import build_pages_grouped_by_warehouse


def _item(
    warehouse: str,
    *,
    article: str,
    nm: int,
    quantity: int,
) -> WBStockItem:
    return WBStockItem(
        lastChangeDate=datetime(2024, 1, 1, 12, 0),
        warehouseName=warehouse,
        supplierArticle=article,
        nmId=nm,
        barcode=f"bc-{nm}",
        quantity=quantity,
        inWayToClient=0,
        inWayFromClient=0,
        quantityFull=quantity,
        category=None,
        subject=None,
        brand=None,
        techSize=None,
        price=None,
        discount=None,
        scCode=None,
    )


def test_page_never_starts_mid_warehouse() -> None:
    items = [
        _item("A", article="A1", nm=1, quantity=5),
        _item("A", article="A2", nm=2, quantity=4),
        _item("A", article="A3", nm=3, quantity=3),
        _item("B", article="B1", nm=4, quantity=2),
    ]

    paged = build_pages_grouped_by_warehouse(items, per_page=3)

    for page in paged.pages:
        assert page.lines[0].startswith("🏬 ")
        assert not page.lines[0].startswith("•")


def test_header_repeats_when_warehouse_spans_pages() -> None:
    items = [_item("A", article=f"A{i}", nm=i, quantity=10 - i) for i in range(1, 6)]

    paged = build_pages_grouped_by_warehouse(items, per_page=3)

    assert len(paged.pages) >= 2
    headers = {page.lines[0] for page in paged.pages}
    assert headers == {"🏬 A"}


def test_page_size_limit() -> None:
    items = [_item("A", article=f"A{i}", nm=i, quantity=5) for i in range(1, 10)]

    paged = build_pages_grouped_by_warehouse(items, per_page=4)

    for page in paged.pages:
        assert len(page.lines) <= 4


def test_page_buttons_windowing() -> None:
    rows = page_buttons(current=8, total=12)
    numbers = [int(button.text) for row in rows for button in row]
    assert numbers == [1, 6, 7, 8, 9, 10, 12]

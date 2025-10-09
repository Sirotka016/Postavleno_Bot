from __future__ import annotations

from datetime import datetime

from postavleno_bot.integrations.wb_client import WBStockItem
from postavleno_bot.services.stocks import build_export_csv, build_export_filename


def _item(
    warehouse: str,
    *,
    article: str,
    nm: int,
    quantity: int,
    price: int | None = None,
    discount: int | None = None,
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
        category="Категория",
        subject="Предмет",
        brand="Бренд",
        techSize="M",
        price=price,
        discount=discount,
        scCode=None,
    )


def test_csv_headers_and_first_row() -> None:
    items = [
        _item("Склад B", article="B", nm=2, quantity=5, price=1000, discount=10),
        _item("Склад A", article="A", nm=1, quantity=7, price=1500, discount=5),
    ]

    csv_data = build_export_csv(items).decode("utf-8").splitlines()

    assert (
        csv_data[0]
        == "Склад;Артикул;nmId;Штрихкод;Кол-во;Категория;Предмет;Бренд;Размер;Цена;Скидка"
    )

    # Sorted by warehouse asc, quantity desc.
    assert csv_data[1] == "Склад A;A;1;bc-1;7;Категория;Предмет;Бренд;M;1500;5"


def test_filename_all_vs_single() -> None:
    moment = datetime(2024, 1, 2, 15, 30)
    assert build_export_filename("ALL", None, moment) == "wb_ostatki_ALL_20240102_1530.csv"
    assert (
        build_export_filename("wh", "Склад Москва", moment)
        == "wb_ostatki_Склад_Москва_20240102_1530.csv"
    )

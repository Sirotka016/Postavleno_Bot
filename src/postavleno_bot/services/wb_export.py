from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from ..integrations.wildberries import WBStockItem
from ..utils.excel import dataframe_to_xlsx_bytes

EXPORT_HEADERS = [
    "Склад",
    "Артикул",
    "nmId",
    "Штрихкод",
    "Кол-во",
    "Категория",
    "Предмет",
    "Бренд",
    "Размер",
    "Цена",
    "Скидка",
]


def _sort_for_export(items: list[WBStockItem]) -> list[WBStockItem]:
    return sorted(
        items,
        key=lambda entry: (
            entry.warehouseName,
            -entry.quantity,
            entry.supplierArticle or "",
            entry.nmId,
        ),
    )


def build_export_dataframe(items: list[WBStockItem]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in _sort_for_export(items):
        rows.append(
            {
                "Склад": item.warehouseName,
                "Артикул": item.supplierArticle,
                "nmId": item.nmId,
                "Штрихкод": item.barcode,
                "Кол-во": item.quantity,
                "Категория": item.category or "",
                "Предмет": item.subject or "",
                "Бренд": item.brand or "",
                "Размер": item.techSize or "",
                "Цена": item.price or "",
                "Скидка": item.discount or "",
            }
        )

    return pd.DataFrame(rows, columns=EXPORT_HEADERS)


def build_export_xlsx(items: list[WBStockItem], *, sheet_name: str) -> bytes:
    dataframe = build_export_dataframe(items)
    return dataframe_to_xlsx_bytes(dataframe, sheet_name=sheet_name)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w]+", "_", value, flags=re.UNICODE)
    cleaned = cleaned.strip("_")
    return cleaned or "warehouse"


def build_export_filename(view: str, warehouse: str | None, moment: datetime) -> str:
    timestamp = moment.strftime("%Y%m%d_%H%M")

    if view == "ALL":
        return f"wb_ostatki_ALL_{timestamp}.xlsx"

    if warehouse:
        sanitized = sanitize_filename(warehouse)
        return f"wb_ostatki_{sanitized}_{timestamp}.xlsx"

    return f"wb_ostatki_{timestamp}.xlsx"

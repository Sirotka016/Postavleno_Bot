from __future__ import annotations

import os

import pandas as pd

from postavleno_bot.core.config import get_settings
from postavleno_bot.services.local import merge_wb_with_local


def _make_wb_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "supplierArticle": ["sku-1", "sku-1", "sku-2"],
            "quantity": [10, 5, 7],
            "brand": ["BrandA", "BrandB", "BrandB"],
            "subject": ["Футболки", "Футболки", "Обувь"],
            "techSize": ["M", "L", "42"],
            "barcode": ["111", "111", "222"],
            "category": ["Одежда", "Одежда", "Обувь"],
            "price": [1000, 1200, 2000],
            "discount": [10, 15, 15],
        }
    )


def _make_local_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Артикул": ["sku-1", "sku-3"],
            "Количество": [4, 8],
        }
    )


def test_wb_dedup_keeps_first_occurrence() -> None:
    wb_df = _make_wb_dataframe()
    local_df = _make_local_dataframe()

    result, stats = merge_wb_with_local(wb_df, local_df, store_name="FootballShop")

    sku1_row = result.loc[result["Артикул"] == "SKU-1"].iloc[0]

    assert len(result) == 2
    assert stats.wb_rows == 3
    assert stats.wb_unique == 2
    assert sku1_row["Бренд"] == "BrandA"
    assert sku1_row["Размер"] == "M"


def test_local_qty_replaces_only_for_matched() -> None:
    wb_df = pd.DataFrame({"supplierArticle": ["sku-1", "sku-2"], "quantity": [5, 9]})
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-3"], "Количество": [3, 7]})

    result, stats = merge_wb_with_local(wb_df, local_df, store_name="FootballShop")

    sku1_qty = result.loc[result["Артикул"] == "SKU-1", "Кол-во_наш_склад"].iloc[0]
    sku2_qty = result.loc[result["Артикул"] == "SKU-2", "Кол-во_наш_склад"].iloc[0]

    assert sku1_qty == 3
    assert sku2_qty == 0
    assert stats.matched_rows == 1
    assert set(result["Артикул"]) == {"SKU-1", "SKU-2"}


def test_result_columns_and_store_name() -> None:
    store_name = "MyLocalStore"
    original = os.environ.get("LOCAL_STORE_NAME")
    os.environ["LOCAL_STORE_NAME"] = store_name
    get_settings.cache_clear()

    wb_df = _make_wb_dataframe()
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-2"], "Количество": [5, 2]})

    result, _ = merge_wb_with_local(wb_df, local_df)

    expected_columns = [
        "Склад",
        "Артикул",
        "nmId",
        "Штрихкод",
        "Кол-во_наш_склад",
        "Категория",
        "Предмет",
        "Бренд",
        "Размер",
        "Цена",
        "Скидка",
    ]

    assert list(result.columns) == expected_columns
    assert set(result["Склад"]) == {store_name}

    if original is None:
        os.environ.pop("LOCAL_STORE_NAME", None)
    else:
        os.environ["LOCAL_STORE_NAME"] = original
    get_settings.cache_clear()

from decimal import Decimal

import pandas as pd

from postavleno_bot.services.store_stock_merge import merge_moysklad_into_wb


def test_merge_updates_quantities_and_store_name() -> None:
    wb_df = pd.DataFrame(
        {
            "Склад": ["WB-1", "WB-2"],
            "Артикул": ["A-1", "B-2"],
            "Кол-во": [3, 4],
            "Цена": [100, 200],
        }
    )
    ms_map = {"A-1": Decimal("7"), "C-3": Decimal("1")}

    merged = merge_moysklad_into_wb(wb_df, ms_map, brand_store="FootballShop")

    assert list(merged["Склад"]) == ["FootballShop", "FootballShop"]
    assert list(merged["Кол-во"]) == [7, 4]
    assert list(merged["Артикул"]) == ["A-1", "B-2"]

    stats = merged.attrs.get("merge_stats")
    assert stats == {"matched": 1, "unmatched": 1, "rows_total": 2}


def test_merge_handles_missing_columns_gracefully() -> None:
    wb_df = pd.DataFrame({"Артикул": ["A"], "Кол-во": [1]})
    merged = merge_moysklad_into_wb(wb_df, {}, brand_store="Demo")
    assert list(merged["Артикул"]) == ["A"]
    assert list(merged["Кол-во"]) == [1]
    assert merged.attrs["merge_stats"]["matched"] == 0

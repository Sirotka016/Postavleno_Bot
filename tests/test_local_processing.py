from __future__ import annotations

import pandas as pd

from postavleno_bot.services.local import classify_dataframe, merge_wb_with_local


def test_classify_wb_vs_local() -> None:
    wb_df = pd.DataFrame(
        {
            "supplierArticle": ["SKU-1"],
            "nmId": [12345],
            "warehouseName": ["Москва"],
            "quantity": [10],
        }
    )

    local_df = pd.DataFrame(
        {
            "Артикул": ["sku-1"],
            "Количество": [5],
        }
    )

    unknown_df = pd.DataFrame({"foo": [1]})

    assert classify_dataframe(wb_df) == "WB"
    assert classify_dataframe(local_df) == "LOCAL"
    assert classify_dataframe(unknown_df) is None


def test_join_keeps_only_wb_articles() -> None:
    wb_df = pd.DataFrame(
        {
            "supplierArticle": ["SKU-1", "SKU-2"],
            "nmId": [111, 222],
            "quantity": [10, 5],
        }
    )

    local_df = pd.DataFrame(
        {
            "Артикул": ["sku-1", "sku-3"],
            "Количество": [4, 9],
        }
    )

    result, stats = merge_wb_with_local(wb_df, local_df, store_name="TestStore")

    assert list(result["Артикул"]) == ["SKU-1", "SKU-2"]
    assert list(result["Кол-во_наш_склад"]) == [4, 0]
    assert stats.wb_rows == 2
    assert stats.wb_unique == 2
    assert stats.local_rows == 2
    assert stats.matched_rows == 1

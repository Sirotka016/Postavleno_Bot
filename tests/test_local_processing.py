from __future__ import annotations

import pandas as pd

from postavleno_bot.services.local import classify_dataframe, perform_join


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
            "warehouseName": ["A", "B"],
            "quantity": [10, 5],
        }
    )

    local_df = pd.DataFrame(
        {
            "Артикул": ["sku-1", "sku-3"],
            "Количество": [4, 9],
        }
    )

    result, stats = perform_join(wb_df, local_df)

    assert list(result["Артикул"]) == ["SKU-1"]
    assert list(result["Количество_склад"]) == [4]
    assert stats.wb_count == 2
    assert stats.matched == 1
    assert stats.dropped == 1

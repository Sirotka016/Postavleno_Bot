from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd


def merge_moysklad_into_wb(
    wb_df: pd.DataFrame, ms_map: dict[str, Decimal], *, brand_store: str
) -> pd.DataFrame:
    result = wb_df.copy()

    if "Склад" in result.columns:
        result.loc[:, "Склад"] = brand_store
    else:  # pragma: no cover - defensive branch for unexpected schema
        result.insert(0, "Склад", brand_store)

    matched = 0
    unmatched = 0

    if "Артикул" not in result.columns or "Кол-во" not in result.columns:
        return result

    for index, article in result["Артикул"].items():
        if article in ms_map:
            quantity = ms_map[article].quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            result.at[index, "Кол-во"] = int(quantity)
            matched += 1
        else:
            unmatched += 1

    result.attrs["merge_stats"] = {
        "matched": matched,
        "unmatched": unmatched,
        "rows_total": len(result),
    }
    return result

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from ..core.logging import get_logger
from ..integrations.moysklad import norm_article

_logger = get_logger(__name__)


def _normalize_map(ms_map: dict[str, Decimal]) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for key, value in ms_map.items():
        normalized[norm_article(str(key))] = Decimal(value)
    return normalized


def _format_quantity(value: Decimal) -> int:
    quantized = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(quantized)


def merge_ms_into_wb(
    wb_df: pd.DataFrame,
    ms_map: dict[str, Decimal],
    *,
    store_name: str,
    qty_col: str,
    art_col: str,
    warehouse_col: str,
) -> pd.DataFrame:
    """Merge MoySklad quantities into a Wildberries-shaped dataframe."""

    result = wb_df.copy()
    normalized_map = _normalize_map(ms_map)
    wb_rows = len(result)
    wb_unique = 0
    replaced = 0

    if warehouse_col in result.columns:
        result.loc[:, warehouse_col] = store_name
    else:
        result[warehouse_col] = store_name

    if art_col not in result.columns or qty_col not in result.columns:
        _logger.info(
            "store.merge.stats",
            outcome="success",
            wb_rows=wb_rows,
            wb_unique=wb_unique,
            ms_found=len(normalized_map),
            replaced=replaced,
        )
        return result

    articles_series = result[art_col]
    relevant_articles = {
        norm_article(str(value))
        for value in articles_series
        if value is not None and not pd.isna(value)
    }
    wb_unique = len(relevant_articles)
    ms_found = sum(1 for key in relevant_articles if key in normalized_map)

    for index, raw_article in result[art_col].items():
        if raw_article is None:
            continue
        article_key = norm_article(str(raw_article))
        ms_value = normalized_map.get(article_key)
        if ms_value is None:
            continue
        result.at[index, qty_col] = _format_quantity(ms_value)
        replaced += 1

    _logger.info(
        "store.merge.stats",
        outcome="success",
        wb_rows=wb_rows,
        wb_unique=wb_unique,
        ms_found=ms_found,
        replaced=replaced,
    )

    return result

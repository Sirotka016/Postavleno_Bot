from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from ..core.logging import get_logger

_MAX_WIDTH = 60
_PADDING = 2


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _estimate_width(series: pd.Series, header: str) -> int:
    header_length = len(str(header))
    values = [_stringify(value) for value in series.tolist()]
    max_value_length = max((len(value) for value in values), default=0)
    if pd.api.types.is_numeric_dtype(series):
        max_value_length = max(max_value_length, 8)
    base = max(header_length, max_value_length)
    return min(base + _PADDING, _MAX_WIDTH)


def _autofit(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    worksheet = writer.sheets[sheet_name]
    for idx, column in enumerate(df.columns):
        width = _estimate_width(df[column], str(column))
        worksheet.set_column(idx, idx, width)


def dataframe_to_xlsx_bytes(df: pd.DataFrame, *, sheet_name: str) -> bytes:
    logger = get_logger(__name__)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        _autofit(writer, sheet_name, df)
    logger.info(
        "export.sent",
        outcome="success",
        rows=len(df.index),
        sheet=sheet_name,
    )
    return buffer.getvalue()


def save_dataframe_to_xlsx(df: pd.DataFrame, *, path: Path, sheet_name: str) -> Path:
    logger = get_logger(__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        _autofit(writer, sheet_name, df)
    logger.info(
        "export.saved",
        outcome="success",
        rows=len(df.index),
        sheet=sheet_name,
        destination=str(path),
    )
    return path

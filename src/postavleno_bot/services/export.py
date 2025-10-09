from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd


def dataframe_to_xlsx_bytes(df: pd.DataFrame, *, sheet_name: str = "Данные") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def save_dataframe_to_xlsx(df: pd.DataFrame, *, path: Path, sheet_name: str = "Данные") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path

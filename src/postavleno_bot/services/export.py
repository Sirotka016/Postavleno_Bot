from __future__ import annotations

from io import BytesIO

import pandas as pd


def dataframe_to_xlsx_bytes(df: pd.DataFrame, *, sheet_name: str = "Данные") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()

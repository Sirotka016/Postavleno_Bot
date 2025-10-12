"""Utilities for preparing Excel exports."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def save_df_xlsx(df: pd.DataFrame, path: Path) -> Path:
    """Persist *df* to *path* with basic styling applied."""

    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_name = "Остатки"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        worksheet = writer.sheets[sheet_name]
        worksheet.freeze_panes = "A2"
        header_font = Font(bold=True)
        for cell in worksheet[1]:
            cell.font = header_font
        for idx, column_cells in enumerate(worksheet.columns, start=1):
            column_letter = get_column_letter(idx)
            max_length = 0
            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 80)
    return path


def _ensure_dataframe(columns: Iterable[str], rows: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=list(columns))
    if df.empty:
        return pd.DataFrame(columns=list(columns))
    return df


def _clean_str_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _clean_int_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    return numeric.astype(int)


def _most_common(series: pd.Series, *, drop_blank: bool = False) -> object:
    cleaned = series.dropna()
    if drop_blank:
        cleaned = cleaned.astype(str).str.strip()
        cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return None
    return cleaned.value_counts().index[0]


def _first_nonempty(series: pd.Series) -> str:
    for value in series:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def wb_to_df_all(items: list[dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(items)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Артикул поставщика",
                "nmId",
                "Штрихкод",
                "Кол-во",
                "В пути к клиенту",
                "Возврат от клиента",
                "Итого",
            ]
        )

    defaults = {
        "supplierArticle": "",
        "nmId": None,
        "barcode": "",
        "quantity": 0,
        "inWayToClient": 0,
        "inWayFromClient": 0,
        "quantityFull": 0,
    }
    for column, default in defaults.items():
        if column not in df:
            df[column] = default

    df["supplierArticle"] = _clean_str_series(df["supplierArticle"])
    df = df[df["supplierArticle"] != ""]
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Артикул поставщика",
                "nmId",
                "Штрихкод",
                "Кол-во",
                "В пути к клиенту",
                "Возврат от клиента",
                "Итого",
            ]
        )
    df["barcode"] = _clean_str_series(df["barcode"])
    df["nmId"] = pd.to_numeric(df["nmId"], errors="coerce")

    for numeric in ["quantity", "inWayToClient", "inWayFromClient", "quantityFull"]:
        df[numeric] = pd.to_numeric(df[numeric], errors="coerce").fillna(0)

    aggregation = (
        df.groupby("supplierArticle")
        .agg(
            nmId=("nmId", lambda s: _most_common(s)),
            barcode=("barcode", _first_nonempty),
            quantity=("quantity", "sum"),
            inWayToClient=("inWayToClient", "sum"),
            inWayFromClient=("inWayFromClient", "sum"),
            quantityFull=("quantityFull", "sum"),
        )
        .reset_index()
    )

    aggregation = aggregation.rename(
        columns={
            "supplierArticle": "Артикул поставщика",
            "nmId": "nmId",
            "barcode": "Штрихкод",
            "quantity": "Кол-во",
            "inWayToClient": "В пути к клиенту",
            "inWayFromClient": "Возврат от клиента",
            "quantityFull": "Итого",
        }
    )

    ordered_columns = [
        "Артикул поставщика",
        "nmId",
        "Штрихкод",
        "Кол-во",
        "В пути к клиенту",
        "Возврат от клиента",
        "Итого",
    ]
    aggregation = aggregation[ordered_columns]
    return aggregation.sort_values("Артикул поставщика", kind="stable").reset_index(drop=True)


def wb_to_df_bywh(items: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        ("warehouseName", "Город склада", _clean_str_series),
        ("supplierArticle", "Артикул поставщика", _clean_str_series),
        ("nmId", "nmId", _clean_int_series),
        ("barcode", "Штрихкод", _clean_str_series),
        ("quantity", "Кол-во", _clean_int_series),
        ("inWayToClient", "В пути к клиенту", _clean_int_series),
        ("inWayFromClient", "Возврат от клиента", _clean_int_series),
        ("quantityFull", "Итого", _clean_int_series),
    ]
    records: list[dict[str, object]] = []
    for payload in items:
        row: dict[str, object] = {}
        if not isinstance(payload, dict):
            payload = {}
        for source, header, _ in columns:
            row[header] = payload.get(source)
        records.append(row)

    headers = [header for _, header, _ in columns]
    df = _ensure_dataframe(headers, records)
    if df.empty:
        return df

    for _, header, cleaner in columns:
        df[header] = cleaner(df[header])

    return df.sort_values(["Город склада", "Артикул поставщика", "nmId"], kind="stable").reset_index(drop=True)


__all__ = [
    "save_df_xlsx",
    "wb_to_df_all",
    "wb_to_df_bywh",
]

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


def _most_common_str(series: pd.Series) -> str:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return ""
    return str(cleaned.value_counts().idxmax())


def _most_common_int(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return 0
    return int(numeric.value_counts().idxmax())


def wb_to_df_all(items: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        "supplierArticle",
        "nmId",
        "barcode",
        "quantity",
        "inWayToClient",
        "inWayFromClient",
        "quantityFull",
    ]
    records: list[dict[str, object]] = []
    for payload in items:
        if not isinstance(payload, dict):
            payload = {}
        records.append({key: payload.get(key) for key in columns})

    df = pd.DataFrame(records, columns=columns)
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

    for column in ["supplierArticle", "barcode"]:
        if column not in df:
            df[column] = ""
    for column in ["nmId", "quantity", "inWayToClient", "inWayFromClient", "quantityFull"]:
        if column not in df:
            df[column] = 0

    df["supplierArticle"] = _clean_str_series(df["supplierArticle"])
    df["barcode"] = _clean_str_series(df["barcode"])
    df["nmId"] = pd.to_numeric(df["nmId"], errors="coerce")
    for numeric in ["quantity", "inWayToClient", "inWayFromClient", "quantityFull"]:
        df[numeric] = pd.to_numeric(df[numeric], errors="coerce").fillna(0)

    aggregated = (
        df.groupby("supplierArticle", as_index=False)
        .agg(
            nmId=("nmId", _most_common_int),
            barcode=("barcode", _most_common_str),
            quantity=("quantity", "sum"),
            inWayToClient=("inWayToClient", "sum"),
            inWayFromClient=("inWayFromClient", "sum"),
            quantityFull=("quantityFull", "sum"),
        )
        .rename(
            columns={
                "supplierArticle": "Артикул поставщика",
                "barcode": "Штрихкод",
                "quantity": "Кол-во",
                "inWayToClient": "В пути к клиенту",
                "inWayFromClient": "Возврат от клиента",
                "quantityFull": "Итого",
            }
        )
    )

    for column in ["Кол-во", "В пути к клиенту", "Возврат от клиента", "Итого"]:
        aggregated[column] = pd.to_numeric(aggregated[column], errors="coerce").fillna(0).astype(int)
    aggregated["nmId"] = pd.to_numeric(aggregated["nmId"], errors="coerce").fillna(0).astype(int)

    ordered_columns = [
        "Артикул поставщика",
        "nmId",
        "Штрихкод",
        "Кол-во",
        "В пути к клиенту",
        "Возврат от клиента",
        "Итого",
    ]
    return aggregated[ordered_columns].sort_values("Артикул поставщика", kind="stable").reset_index(drop=True)


def wb_to_df_bywh(items: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        ("warehouseName", "Склад", _clean_str_series),
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

    return df.sort_values(["Склад", "Артикул поставщика", "nmId"], kind="stable").reset_index(drop=True)


__all__ = [
    "save_df_xlsx",
    "wb_to_df_all",
    "wb_to_df_bywh",
]

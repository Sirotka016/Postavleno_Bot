"""Utilities for preparing Excel exports."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def save_df_xlsx(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
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


def wb_to_df_all(items: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        ("supplierArticle", "Артикул"),
        ("nmId", "nmId"),
        ("barcode", "ШК"),
        ("quantity", "На складе"),
        ("inWayToClient", "В пути к клиенту"),
        ("inWayFromClient", "Возврат от клиента"),
        ("quantityFull", "Доступно (итого)"),
    ]
    records: list[dict[str, object]] = []
    for payload in items:
        row: dict[str, object] = {}
        for source, header in columns:
            value = payload.get(source) if isinstance(payload, dict) else None
            row[header] = value
        records.append(row)

    headers = [header for _, header in columns]
    df = _ensure_dataframe(headers, records)
    if df.empty:
        return df

    df["Артикул"] = _clean_str_series(df["Артикул"])
    df["nmId"] = _clean_int_series(df["nmId"])
    df["ШК"] = _clean_str_series(df["ШК"])

    for header in [
        "На складе",
        "В пути к клиенту",
        "Возврат от клиента",
        "Доступно (итого)",
    ]:
        df[header] = _clean_int_series(df[header])

    return df.sort_values(["Артикул", "nmId"], kind="stable").reset_index(drop=True)


def wb_to_df_bywh(items: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        ("warehouseName", "Склад"),
        ("supplierArticle", "Артикул"),
        ("nmId", "nmId"),
        ("barcode", "ШК"),
        ("quantity", "На складе"),
        ("inWayToClient", "В пути к клиенту"),
        ("inWayFromClient", "Возврат от клиента"),
        ("quantityFull", "Доступно (итого)"),
    ]
    records: list[dict[str, object]] = []
    for payload in items:
        row: dict[str, object] = {}
        for source, header in columns:
            value = payload.get(source) if isinstance(payload, dict) else None
            row[header] = value
        records.append(row)

    headers = [header for _, header in columns]
    df = _ensure_dataframe(headers, records)
    if df.empty:
        return df

    df["Склад"] = _clean_str_series(df["Склад"])
    df["Артикул"] = _clean_str_series(df["Артикул"])
    df["nmId"] = _clean_int_series(df["nmId"])
    df["ШК"] = _clean_str_series(df["ШК"])

    for header in [
        "На складе",
        "В пути к клиенту",
        "Возврат от клиента",
        "Доступно (итого)",
    ]:
        df[header] = _clean_int_series(df[header])

    return df.sort_values(["Склад", "Артикул", "nmId"], kind="stable").reset_index(drop=True)


def ms_to_df_all(payload: dict[str, object] | None) -> pd.DataFrame:
    rows = []
    if isinstance(payload, dict):
        raw_rows = payload.get("rows")
        if isinstance(raw_rows, list):
            for entry in raw_rows:
                if not isinstance(entry, dict):
                    continue
                rows.append(
                    {
                        "Артикул": entry.get("article"),
                        "Наименование": entry.get("name"),
                        "Остаток": entry.get("stock"),
                        "Резерв": entry.get("reserve"),
                        "Ожидание": entry.get("inTransit"),
                        "Доступно": entry.get("quantity"),
                    }
                )

    headers = ["Артикул", "Наименование", "Остаток", "Резерв", "Ожидание", "Доступно"]
    df = _ensure_dataframe(headers, rows)
    if df.empty:
        return df

    df["Артикул"] = _clean_str_series(df["Артикул"])
    df["Наименование"] = _clean_str_series(df["Наименование"])

    for header in ["Остаток", "Резерв", "Ожидание", "Доступно"]:
        df[header] = _clean_int_series(df[header])

    return df.sort_values(["Артикул", "Наименование"], kind="stable").reset_index(drop=True)


__all__ = [
    "ms_to_df_all",
    "save_df_xlsx",
    "wb_to_df_all",
    "wb_to_df_bywh",
]

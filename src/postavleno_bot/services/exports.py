"""Services for preparing stock export files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations import fetch_ms_stocks_all, fetch_wb_stocks_all

_logger = get_logger("stocks.export")


@dataclass(slots=True)
class ExportResult:
    path: Path
    rows: int
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


def _exports_dir(login: str) -> Path:
    base = get_settings().accounts_dir / login / "exports"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _timestamp() -> datetime:
    return datetime.now(UTC).astimezone()


def _format_filename(prefix: str, created_at: datetime) -> str:
    return f"{prefix}_{created_at.strftime('%Y%m%d_%H%M')}.xlsx"


def _serialize(value: Any) -> Any:
    if isinstance(value, dict | list | tuple | set):
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except TypeError:  # pragma: no cover - fallback
            return str(value)
    return value


def _serialize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: _serialize(val) for key, val in record.items()}
        for record in records
    ]


async def export_wb_stocks_all(login: str, wb_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_stocks_all"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_wb_stocks_all(wb_token)
    records = [item.to_dict() for item in items]
    serialized = _serialize_records(records)
    df = pd.DataFrame(serialized)
    df.to_excel(file_path, index=False)

    result = ExportResult(path=file_path, rows=len(df), created_at=created_at)
    _logger.info(
        "export.ready",
        kind="wb_all",
        rows=result.rows,
        file=str(file_path),
        outcome="success",
    )
    return result


async def export_wb_stocks_by_warehouse(login: str, wb_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_stocks_by_warehouse"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_wb_stocks_all(wb_token)
    records = [item.to_dict() for item in items]
    df = pd.DataFrame(_serialize_records(records))

    if df.empty:
        grouped = pd.DataFrame(columns=["Город", "Артикул", "Кол-во"])
        warehouse_count = 0
    else:
        warehouse_col = next(
            (col for col in df.columns if col in {"warehouseName", "warehouse", "warehouse_name", "officeName"}),
            "warehouseName",
        )
        supplier_col = next(
            (col for col in df.columns if col in {"supplierArticle", "vendorCode", "article"}),
            "supplierArticle",
        )
        quantity_col = next(
            (
                col
                for col in (
                    "quantity",
                    "stock",
                    "stocks",
                    "qty",
                    "amount",
                    "quantityFull",
                    "quantityNotInOrders",
                )
                if col in df.columns
            ),
            None,
        )
        quantities = (
            pd.to_numeric(df[quantity_col], errors="coerce") if quantity_col else pd.Series([0] * len(df))
        )
        grouped = (
            pd.DataFrame(
                {
                    "Город": df.get(warehouse_col, pd.Series([""] * len(df))).fillna("").astype(str).str.strip(),
                    "Артикул": df.get(supplier_col, pd.Series([""] * len(df))).fillna("").astype(str).str.strip(),
                    "Кол-во": quantities.fillna(0.0),
                }
            )
            .groupby(["Город", "Артикул"], as_index=False)["Кол-во"]
            .sum()
        )
        grouped["Кол-во"] = grouped["Кол-во"].round().astype(int)
        grouped = grouped[grouped["Кол-во"] > 0].sort_values(["Город", "Артикул"]).reset_index(drop=True)
        warehouse_count = grouped["Город"].nunique()

    grouped.to_excel(file_path, index=False)

    result = ExportResult(
        path=file_path,
        rows=len(grouped),
        created_at=created_at,
        metadata={"warehouses": warehouse_count},
    )
    _logger.info(
        "export.ready",
        kind="wb_by_wh",
        rows=result.rows,
        file=str(file_path),
        warehouses=warehouse_count,
        outcome="success",
    )
    return result


def _flatten_barcodes(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                for key in ("ean13", "gtin", "code", "value"):
                    code = item.get(key)
                    if code:
                        parts.append(str(code))
                        break
            elif item is not None:
                parts.append(str(item))
        return ", ".join(parts)
    if value is None:
        return ""
    return str(value)


async def export_ms_stocks_all(login: str, ms_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "ms_stocks_all"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_ms_stocks_all(ms_token)
    df = pd.json_normalize(items) if items else pd.DataFrame()

    if not df.empty:
        if "barcodes" in df.columns:
            df["barcodes"] = df["barcodes"].apply(_flatten_barcodes)
        selected_columns = {
            "article": "Артикул",
            "name": "Название",
            "externalCode": "Внешний код",
            "barcodes": "Штрихкоды",
            "productFolder.name": "Группа",
            "stock": "На складе",
            "reserve": "В резерве",
            "inTransit": "В пути",
            "quantity": "Всего",
            "available": "Доступно",
            "updated": "Обновлено",
        }
        for column in selected_columns:
            if column not in df.columns:
                df[column] = None
        export_df = df[list(selected_columns.keys())].rename(columns=selected_columns)
    else:
        export_df = pd.DataFrame(
            columns=[
                "Артикул",
                "Название",
                "Внешний код",
                "Штрихкоды",
                "Группа",
                "На складе",
                "В резерве",
                "В пути",
                "Всего",
                "Доступно",
                "Обновлено",
            ]
        )

    export_df.to_excel(file_path, index=False)

    result = ExportResult(path=file_path, rows=len(export_df), created_at=created_at)
    _logger.info(
        "export.ready",
        kind="ms_all",
        rows=result.rows,
        file=str(file_path),
        outcome="success",
    )
    return result


__all__ = [
    "ExportResult",
    "export_wb_stocks_all",
    "export_wb_stocks_by_warehouse",
    "export_ms_stocks_all",
]

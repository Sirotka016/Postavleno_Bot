"""Services for preparing stock export files."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations import fetch_ms_stocks_all, fetch_wb_stocks_all
from ..utils.excel import ms_to_df_all, save_df_xlsx, wb_to_df_bywh

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


WB_ALL_AGG_COLUMNS = [
    "Артикул поставщика",
    "nmId",
    "Штрихкод",
    "Кол-во",
    "В пути к клиенту",
    "Возврат от клиента",
    "Итого",
]


def _ensure_required_columns(df: pd.DataFrame, columns: Iterable[str], *, fill: Any = 0) -> None:
    for column in columns:
        if column not in df.columns:
            df[column] = fill


def wb_to_df_all_agg(payload: list[dict[str, Any]] | None) -> pd.DataFrame:
    records = [item for item in (payload or []) if isinstance(item, dict)]
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=WB_ALL_AGG_COLUMNS)

    _ensure_required_columns(df, ["supplierArticle", "barcode"], fill="")
    _ensure_required_columns(
        df,
        ["nmId", "quantity", "inWayToClient", "inWayFromClient", "quantityFull"],
        fill=0,
    )

    df["supplierArticle"] = df["supplierArticle"].fillna("").astype(str).str.strip()
    df["barcode"] = df["barcode"].fillna("").astype(str).str.strip()
    df["nmId"] = pd.to_numeric(df["nmId"], errors="coerce").fillna(0).astype(int)
    for numeric in ["quantity", "inWayToClient", "inWayFromClient", "quantityFull"]:
        df[numeric] = pd.to_numeric(df[numeric], errors="coerce").fillna(0)

    aggregated = (
        df.groupby(["supplierArticle", "nmId"], as_index=False)
        .agg(
            {
                "barcode": "first",
                "quantity": "sum",
                "inWayToClient": "sum",
                "inWayFromClient": "sum",
                "quantityFull": "sum",
            }
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

    ordered = aggregated[WB_ALL_AGG_COLUMNS]
    return ordered.sort_values(["Артикул поставщика", "nmId"], kind="stable").reset_index(drop=True)


async def export_wb_stocks_all(login: str, wb_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_ostatki_ALL"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_wb_stocks_all(wb_token)
    payloads = [item.to_dict() for item in items]
    df = wb_to_df_all_agg(payloads)
    save_df_xlsx(df, file_path)

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
    prefix = "wb_ostatki_BY_WAREHOUSE"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_wb_stocks_all(wb_token)
    payloads = [item.to_dict() for item in items]
    df = wb_to_df_bywh(payloads)
    save_df_xlsx(df, file_path)

    warehouses = int(df["Склад"].nunique()) if not df.empty else 0
    result = ExportResult(
        path=file_path,
        rows=len(df),
        created_at=created_at,
        metadata={"warehouses": warehouses},
    )
    _logger.info(
        "export.ready",
        kind="wb_by_wh",
        rows=result.rows,
        file=str(file_path),
        warehouses=warehouses,
        outcome="success",
    )
    return result


async def export_ms_stocks_all(login: str, ms_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "ms_ostatki_ALL"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    payload = await fetch_ms_stocks_all(ms_token)
    df = ms_to_df_all(payload)
    save_df_xlsx(df, file_path)

    result = ExportResult(path=file_path, rows=len(df), created_at=created_at)
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
    "wb_to_df_all_agg",
]

"""Services for preparing stock export files."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from ..core.config import get_settings
from ..core.logging import get_logger
from ..utils.excel import save_df_xlsx, wb_to_df_all, wb_to_df_bywh
from .wb_cache import load_wb_rows

_logger = get_logger("stocks.export")


def _log_stage(stage: str, start: float, **fields: Any) -> None:
    duration_ms = (perf_counter() - start) * 1000
    payload = {"stage": stage, "duration_ms": round(duration_ms, 2), **fields}
    _logger.info("perf.stage", **payload)


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


async def export_wb_stocks_all(login: str, wb_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_ostatki_ALL"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    fetch_start = perf_counter()
    rows = await load_wb_rows(login, wb_token)
    _log_stage("fetch", fetch_start, records_count=len(rows), kind="wb_all")

    transform_start = perf_counter()
    df = await asyncio.to_thread(wb_to_df_all, rows)
    _log_stage("transform", transform_start, records_count=len(df), kind="wb_all")

    write_start = perf_counter()
    await asyncio.to_thread(save_df_xlsx, df, file_path)
    _log_stage("write", write_start, records_count=len(df), kind="wb_all")

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

    fetch_start = perf_counter()
    rows = await load_wb_rows(login, wb_token)
    _log_stage("fetch", fetch_start, records_count=len(rows), kind="wb_by_wh")

    transform_start = perf_counter()
    df = await asyncio.to_thread(wb_to_df_bywh, rows)
    _log_stage("transform", transform_start, records_count=len(df), kind="wb_by_wh")

    write_start = perf_counter()
    await asyncio.to_thread(save_df_xlsx, df, file_path)
    _log_stage("write", write_start, records_count=len(df), kind="wb_by_wh")

    warehouses = int(df["Город склада"].nunique()) if not df.empty else 0
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


__all__ = [
    "ExportResult",
    "export_wb_stocks_all",
    "export_wb_stocks_by_warehouse",
    "wb_to_df_all",
]

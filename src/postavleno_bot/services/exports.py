"""Export helpers for preparing XLSX reports."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import pandas as pd

from ..core.config import get_settings
from ..core.logging import get_logger
from ..utils.excel import save_df_xlsx, wb_to_df_all, wb_to_df_bywh
from .wb_cache import load_wb_rows

_logger = get_logger("stocks.export")

_DF_CACHE: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}


def _cache_ttl() -> int:
    value = getattr(get_settings(), "cache_ttl_seconds", 60)
    return max(5, int(value or 0))


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


async def _build_dataframe(
    *,
    login: str,
    token: str,
    mode: str,
    bypass_cache: bool,
    builder: Callable[[list[dict[str, Any]]], pd.DataFrame],
) -> pd.DataFrame:
    cache_key = (token, mode)
    ttl = _cache_ttl()
    now = time.monotonic()

    if not bypass_cache:
        cached = _DF_CACHE.get(cache_key)
        if cached and now - cached[0] < ttl:
            df = cached[1]
            _logger.info("export.cache_hit", kind=mode, rows=int(getattr(df, "shape", (0,))[0]))
            return df.copy()

    fetch_start = perf_counter()
    rows = await load_wb_rows(login, token, bypass_cache=bypass_cache)
    _log_stage(
        "fetch",
        fetch_start,
        records_count=len(rows),
        kind=mode,
        cache="bypass" if bypass_cache else "miss",
    )

    transform_start = perf_counter()
    df = await asyncio.to_thread(builder, rows)
    _log_stage("transform", transform_start, records_count=len(df), kind=mode)

    _DF_CACHE[cache_key] = (time.monotonic(), df)
    return df.copy()


async def export_wb_stocks_all(
    login: str,
    wb_token: str,
    *,
    bypass_cache: bool = False,
) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_ostatki_ALL"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    df = await _build_dataframe(
        login=login,
        token=wb_token,
        mode="wb_all",
        bypass_cache=bypass_cache,
        builder=wb_to_df_all,
    )

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
        cache_bypass=bypass_cache,
    )
    return result


async def export_wb_stocks_by_warehouse(
    login: str,
    wb_token: str,
    *,
    bypass_cache: bool = False,
) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_ostatki_BY_WAREHOUSE"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    df = await _build_dataframe(
        login=login,
        token=wb_token,
        mode="wb_by_wh",
        bypass_cache=bypass_cache,
        builder=wb_to_df_bywh,
    )

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
        cache_bypass=bypass_cache,
    )
    return result


__all__ = [
    "ExportResult",
    "export_wb_stocks_all",
    "export_wb_stocks_by_warehouse",
    "wb_to_df_all",
]

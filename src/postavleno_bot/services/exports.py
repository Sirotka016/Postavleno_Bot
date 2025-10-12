"""Services for preparing stock export files."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from ..core.logging import get_logger
from ..integrations import fetch_wb_stocks_all
from ..utils.excel import save_df_xlsx, wb_to_df_all, wb_to_df_bywh

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


async def export_wb_stocks_all(login: str, wb_token: str) -> ExportResult:
    created_at = _timestamp()
    prefix = "wb_ostatki_ALL"
    file_path = _exports_dir(login) / _format_filename(prefix, created_at)

    items = await fetch_wb_stocks_all(wb_token)
    payloads = [item.to_dict() for item in items]
    df = wb_to_df_all(payloads)
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


__all__ = [
    "ExportResult",
    "export_wb_stocks_all",
    "export_wb_stocks_by_warehouse",
    "wb_to_df_all",
]

"""Handlers for stock export buttons in the home menu."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from ..core.logging import get_logger
from ..services.exports import (
    ExportResult,
    export_wb_stocks_all,
    export_wb_stocks_by_warehouse,
)
from .pages import (
    render_export_error,
    render_export_missing_token,
    render_export_progress,
    render_export_ready,
    render_home,
    render_require_auth,
)
from .utils import load_active_profile

router = Router()

_logger = get_logger(__name__).bind(handler="menu")
_export_logger = get_logger("stocks.export")


def _format_created(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _summary_for_result(kind: str, result: ExportResult) -> str:
    created = _format_created(result.created_at)
    if kind == "wb_by_wh":
        warehouses = int(result.metadata.get("warehouses", 0))
        return f"Складов {warehouses}, строк {result.rows} ({created})"
    return f"Строк {result.rows} ({created})"


async def _handle_export(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    kind: str,
    token_attr: str,
    service_label: str,
    exporter: Callable[[str, str], Awaitable[ExportResult]],
) -> None:
    if callback.message is None:
        return

    await callback.answer("Готовлю файл…")
    await state.set_state(None)

    profile = await load_active_profile(state)
    chat_id = callback.message.chat.id
    bot = callback.bot

    if not profile:
        await render_require_auth(bot, state, chat_id, nav_action="replace")
        return

    token = getattr(profile, token_attr, None)
    if not token:
        await render_export_missing_token(bot, state, chat_id, service=service_label, nav_action="push")
        return

    await render_export_progress(bot, state, chat_id, kind=kind, nav_action="push")

    try:
        result: ExportResult = await exporter(profile.username, token)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("export failed", kind=kind, error=str(exc))
        _export_logger.error(
            "export.failed",
            kind=kind,
            rows=0,
            file=None,
            outcome="error",
            error=str(exc),
        )
        await render_export_error(bot, state, chat_id, kind=kind, nav_action="replace")
        return

    try:
        await bot.send_document(chat_id, FSInputFile(result.path))
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("failed to send export", kind=kind, error=str(exc))
        _export_logger.error(
            "export.delivery_failed",
            kind=kind,
            rows=result.rows,
            file=str(result.path),
            outcome="error",
            error=str(exc),
        )
        await render_export_error(bot, state, chat_id, kind=kind, nav_action="replace")
        return

    await callback.answer(_summary_for_result(kind, result))
    await render_export_ready(
        bot,
        state,
        chat_id,
        kind=kind,
        nav_action="replace",
    )


@router.callback_query(F.data == "stocks_wb_all")
async def handle_wb_all(callback: CallbackQuery, state: FSMContext) -> None:
    await _handle_export(
        callback,
        state,
        kind="wb_all",
        token_attr="wb_api",
        service_label="WB",
        exporter=export_wb_stocks_all,
    )


@router.callback_query(F.data == "stocks_wb_bywh")
async def handle_wb_by_warehouse(callback: CallbackQuery, state: FSMContext) -> None:
    await _handle_export(
        callback,
        state,
        kind="wb_by_wh",
        token_attr="wb_api",
        service_label="WB",
        exporter=export_wb_stocks_by_warehouse,
    )


__all__ = ["router"]

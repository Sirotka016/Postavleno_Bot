"""Handlers for email verification flow."""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..core.logging import get_logger
from ..domain import validate_email
from ..services.email_verification import start_email_verification, verify_email_code
from ..state import EditEmailState
from .pages import render_edit_email, render_profile, render_require_auth
from .utils import delete_user_message, load_active_profile

router = Router()

_logger = get_logger(__name__).bind(handler="email")


@router.message(EditEmailState.await_email)
async def handle_email_input(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    email = (message.text or "").strip()
    if not validate_email(email):
        await render_edit_email(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt="Похоже, это не e-mail. Попробуйте ещё раз.",
        )
        return

    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    try:
        updated = await start_email_verification(profile, email)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.exception("failed to send verification email", error=str(exc))
        await render_edit_email(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            prompt=(
                "Не получилось отправить письмо 😔\n"
                "Проверьте корректность почты и попробуйте ещё раз.\n"
                "Если не помогло — напишите нам, укажем альтернативный способ подтверждения."
            ),
        )
        return

    await state.set_state(EditEmailState.await_code)
    await render_edit_email(
        message.bot,
        state,
        message.chat.id,
        nav_action="replace",
        await_code=True,
        email=updated.email,
        prompt="Введите шестизначный код из письма.",
    )


@router.message(EditEmailState.await_code)
async def handle_code_input(message: Message, state: FSMContext) -> None:
    await delete_user_message(message)
    code = (message.text or "").strip()
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(message.bot, state, message.chat.id, nav_action="replace")
        return

    if not code.isdigit() or len(code) != 6:
        await render_edit_email(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            await_code=True,
            email=profile.email,
            prompt="Код должен состоять из 6 цифр.",
        )
        return

    success, updated = verify_email_code(profile, code)
    if not success:
        await render_edit_email(
            message.bot,
            state,
            message.chat.id,
            nav_action="replace",
            await_code=True,
            email=profile.email,
            prompt="Код не подошёл или устарел. Запросите новый через кнопку «Почта».",
        )
        return

    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Почта подтверждена ✅",
    )


__all__ = ["router"]

"""Handlers for the email binding flow."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..core.logging import get_logger
from ..domain import validate_email
from ..services.accounts import get_accounts_repo
from ..services.email_verification import start_email_verification, verify_email_code
from ..state import EmailStates
from .pages import (
    render_edit_email,
    render_email_menu,
    render_email_unlink_confirm,
    render_profile,
    render_require_auth,
)
from .utils import delete_user_message, load_active_profile

router = Router()

logger = get_logger(__name__).bind(handler="email")


async def _ensure_profile(callback: CallbackQuery, state: FSMContext):
    profile = await load_active_profile(state)
    if not profile:
        await render_require_auth(callback.bot, state, callback.message.chat.id, nav_action="replace")
    return profile


@router.callback_query(F.data == "email.open")
async def open_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    if not profile.email:
        await state.set_state(EmailStates.waiting_email)
        await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="push")
        return

    await render_email_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="push",
    )


@router.callback_query(F.data == "email.change")
async def change_email(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(EmailStates.waiting_email)
    await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "email.unlink_confirm")
async def unlink_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    await state.set_state(None)
    await render_email_unlink_confirm(callback.bot, state, callback.message.chat.id, nav_action="replace")


@router.callback_query(F.data == "email.unlink_no")
async def cancel_unlink(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    if not profile.email:
        await state.set_state(EmailStates.waiting_email)
        await render_edit_email(callback.bot, state, callback.message.chat.id, nav_action="replace")
        return

    await state.set_state(None)
    await render_email_menu(
        callback.bot,
        state,
        callback.message.chat.id,
        profile=profile,
        nav_action="replace",
    )


@router.callback_query(F.data == "email.unlink_yes")
async def confirm_unlink(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return

    await callback.answer()
    profile = await _ensure_profile(callback, state)
    if not profile:
        return

    repo = get_accounts_repo()
    updated = repo.update_fields(
        profile.username,
        email=None,
        email_verified=False,
        email_pending_hash=None,
        email_pending_expires_at=None,
    )

    await state.set_state(None)
    await render_profile(
        callback.bot,
        state,
        callback.message.chat.id,
        updated,
        nav_action="replace",
        extra="Почта отвязана ✅",
    )


@router.message(EmailStates.waiting_email)
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
        logger.exception("failed to send verification email", error=str(exc))
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

    await state.set_state(EmailStates.waiting_code)
    await render_edit_email(
        message.bot,
        state,
        message.chat.id,
        nav_action="replace",
        await_code=True,
        email=updated.email,
        prompt="Код действителен 10 минут.",
    )


@router.message(EmailStates.waiting_code)
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
            prompt="Код неверный или истёк. Попробуйте снова.",
        )
        return

    await state.set_state(None)
    await render_profile(
        message.bot,
        state,
        message.chat.id,
        updated,
        nav_action="replace",
        extra="Готово! Почта подтверждена ✅",
    )


__all__ = ["router"]

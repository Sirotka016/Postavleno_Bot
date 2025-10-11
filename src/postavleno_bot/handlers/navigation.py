"""Navigation helpers such as the back button."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_EDIT_EMAIL,
    SCREEN_EDIT_MS,
    SCREEN_EDIT_WB,
    SCREEN_HOME,
    SCREEN_LOGIN,
    SCREEN_PROFILE,
    SCREEN_REGISTER,
    nav_back,
)
from ..services.accounts import AccountNotFoundError, get_accounts_repo
from ..state import EditMSState, EditWBState, LoginStates, RegisterStates
from .pages import (
    render_auth_menu,
    render_edit_email,
    render_edit_ms,
    render_edit_wb,
    render_home,
    render_login,
    render_profile,
    render_register,
)
from .utils import get_auth_user, set_auth_user

router = Router()


@router.callback_query(F.data == "nav.back")
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await state.set_state(None)
    previous = await nav_back(state)
    bot = callback.bot
    chat_id = callback.message.chat.id
    if not previous:
        await render_home(bot, state, chat_id, nav_action="root")
        return

    repo = get_accounts_repo()
    auth_user = await get_auth_user(state)

    if previous.name == SCREEN_HOME:
        await render_home(bot, state, chat_id, nav_action="root")
    elif previous.name == SCREEN_AUTH_MENU:
        await render_auth_menu(bot, state, chat_id, nav_action="replace")
    elif previous.name == SCREEN_LOGIN:
        await state.set_state(LoginStates.await_login)
        await render_login(
            bot,
            state,
            chat_id,
            nav_action="replace",
            await_password=bool(previous.params.get("await_password")),
        )
    elif previous.name == SCREEN_REGISTER:
        await state.set_state(RegisterStates.await_login)
        await render_register(
            bot,
            state,
            chat_id,
            nav_action="replace",
            await_password=bool(previous.params.get("await_password")),
        )
    elif previous.name == SCREEN_PROFILE and auth_user:
        try:
            profile = repo.get(auth_user)
        except AccountNotFoundError:
            await set_auth_user(state, None)
            await render_home(bot, state, chat_id, nav_action="root")
        else:
            await render_profile(bot, state, chat_id, profile, nav_action="replace")
    elif previous.name == SCREEN_EDIT_WB:
        await state.set_state(EditWBState.await_token)
        await render_edit_wb(bot, state, chat_id, nav_action="replace")
    elif previous.name == SCREEN_EDIT_MS:
        await state.set_state(EditMSState.await_token)
        await render_edit_ms(bot, state, chat_id, nav_action="replace")
    elif previous.name == SCREEN_EDIT_EMAIL:
        await render_edit_email(bot, state, chat_id, nav_action="replace")
    else:
        await render_home(bot, state, chat_id, nav_action="root")

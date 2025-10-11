"""Rendering helpers for bot screens."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_EDIT_EMAIL,
    SCREEN_EDIT_MS,
    SCREEN_EDIT_WB,
    SCREEN_HOME,
    SCREEN_LOGIN,
    SCREEN_PROFILE,
    SCREEN_REGISTER,
    SCREEN_UNKNOWN,
    ScreenState,
    nav_push,
    nav_replace,
    nav_root,
)
from ..services.accounts import AccountProfile
from ..ui import (
    card_manager,
    kb_auth_menu,
    kb_edit_email,
    kb_edit_ms,
    kb_edit_wb,
    kb_home,
    kb_login,
    kb_profile,
    kb_register,
    kb_retry_login,
    kb_retry_register,
    kb_unknown,
)

HOME_TEXT = (
    "Привет! Я Postavleno_Bot.\n"
    "Скоро здесь появится вся нужная информация. А пока — начните с авторизации."
)

AUTH_MENU_TEXT = (
    "🔐 Авторизация\n\n"
    "Вы можете войти в существующий аккаунт или создать новый.\n\n"
    "• Авторизация — введите логин и пароль.\n"
    "• Регистрация — придумайте логин и пароль.\n\n"
    "Логин: латиница, цифры, точка, дефис, подчёркивание (3–32).\n"
    "Пароль: минимум 6 символов."
)

LOGIN_TEXT = "🔑 Вход в аккаунт\n\nВведите логин."
LOGIN_PASSWORD_TEXT = "🔑 Вход в аккаунт\n\nВведите пароль."
REGISTER_TEXT = (
    "🆕 Регистрация\n\n"
    "Придумайте логин: латиница, цифры, точка, дефис, подчёркивание (3–32)."
)
REGISTER_PASSWORD_TEXT = "🆕 Регистрация\n\nВведите пароль (≥ 6 символов)."
EDIT_WB_TEXT = "🔧 Смена WB API ключа\n\nОтправьте новый ключ."
EDIT_MS_TEXT = "🔧 Смена «Мой Склад» API ключа\n\nОтправьте новый ключ."
EDIT_EMAIL_TEXT = "📧 Почта\n\nСкоро здесь появится подтверждение email."
LOGIN_ERROR_TEXT = "Аккаунт не найден."
REGISTER_TAKEN_TEXT = "Логин занят, придумайте другой."
SUCCESS_SAVED = "Сохранено."
UNKNOWN_TEXT = "Я не понял запрос 🤔\nВыберите действие:"


async def _apply_nav(state: FSMContext, action: str, screen: ScreenState) -> None:
    if action == "root":
        await nav_root(state, screen)
    elif action == "push":
        await nav_push(state, screen)
    else:
        await nav_replace(state, screen)


async def render_home(bot: Bot, state: FSMContext, chat_id: int, *, nav_action: str = "root") -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_HOME))
    return await card_manager.render(bot, chat_id, HOME_TEXT, reply_markup=kb_home(), state=state)


async def render_auth_menu(
    bot: Bot, state: FSMContext, chat_id: int, *, nav_action: str = "replace"
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_AUTH_MENU))
    return await card_manager.render(
        bot,
        chat_id,
        AUTH_MENU_TEXT,
        reply_markup=kb_auth_menu(),
        state=state,
    )


async def render_login(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "replace",
    await_password: bool = False,
    prompt: str | None = None,
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_LOGIN, {"await_password": await_password}),
    )
    text = LOGIN_PASSWORD_TEXT if await_password else LOGIN_TEXT
    if prompt:
        text = f"{text}\n\n{prompt}"
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_login(), state=state)


async def render_login_error(bot: Bot, state: FSMContext, chat_id: int) -> int:
    await _apply_nav(state, "replace", ScreenState(SCREEN_LOGIN, {"error": True}))
    return await card_manager.render(
        bot,
        chat_id,
        f"{LOGIN_TEXT}\n\n{LOGIN_ERROR_TEXT}",
        reply_markup=kb_retry_login(),
        state=state,
    )


async def render_register(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "replace",
    await_password: bool = False,
    prompt: str | None = None,
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_REGISTER, {"await_password": await_password}),
    )
    text = REGISTER_PASSWORD_TEXT if await_password else REGISTER_TEXT
    if prompt:
        text = f"{text}\n\n{prompt}"
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_register(), state=state)


async def render_register_taken(bot: Bot, state: FSMContext, chat_id: int) -> int:
    await _apply_nav(state, "replace", ScreenState(SCREEN_REGISTER, {"error": True}))
    return await card_manager.render(
        bot,
        chat_id,
        f"{REGISTER_TEXT}\n\n{REGISTER_TAKEN_TEXT}",
        reply_markup=kb_retry_register(),
        state=state,
    )


def _format_datetime(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


async def render_profile(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    profile: AccountProfile,
    *,
    nav_action: str = "replace",
    extra: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_PROFILE))
    wb_state = "✅ подключен" if profile.wb_api else "—"
    ms_state = "✅ подключен" if profile.ms_api else "—"
    email = profile.email or "—"
    company = profile.company_name or profile.display_login
    lines = [
        "👤 Профиль",
        "",
        f"Компания: {company}",
        f"Логин: {profile.display_login}",
        f"Дата регистрации: {_format_datetime(profile.created_at)}",
        "",
        f"Почта: {email}",
        "",
        f"WB API: {wb_state}",
        f"МойСклад API: {ms_state}",
    ]
    if extra:
        lines.extend(["", extra])
    text = "\n".join(lines)
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_profile(), state=state)


async def render_edit_wb(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    prompt: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_WB))
    text = EDIT_WB_TEXT if not prompt else f"{EDIT_WB_TEXT}\n\n{prompt}"
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_edit_wb(), state=state)


async def render_edit_ms(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    prompt: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_MS))
    text = EDIT_MS_TEXT if not prompt else f"{EDIT_MS_TEXT}\n\n{prompt}"
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_edit_ms(), state=state)


async def render_edit_email(
    bot: Bot, state: FSMContext, chat_id: int, *, nav_action: str = "push"
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_EMAIL))
    return await card_manager.render(
        bot,
        chat_id,
        EDIT_EMAIL_TEXT,
        reply_markup=kb_edit_email(),
        state=state,
    )


async def render_unknown(
    bot: Bot, state: FSMContext, chat_id: int, *, nav_action: str = "push"
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_UNKNOWN))
    return await card_manager.render(
        bot,
        chat_id,
        UNKNOWN_TEXT,
        reply_markup=kb_unknown(),
        state=state,
    )

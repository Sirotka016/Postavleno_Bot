"""Rendering helpers for bot screens."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.fsm.context import FSMContext

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_DELETE_CONFIRM,
    SCREEN_EDIT_COMPANY,
    SCREEN_EDIT_EMAIL,
    SCREEN_EDIT_MS,
    SCREEN_EDIT_WB,
    SCREEN_EXPORT_DONE,
    SCREEN_EXPORT_STATUS,
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
    kb_delete_confirm,
    kb_delete_error,
    kb_edit_company,
    kb_edit_email,
    kb_edit_ms,
    kb_edit_wb,
    kb_export_error,
    kb_export_missing_token,
    kb_export_ready,
    kb_home,
    kb_login,
    kb_profile,
    kb_register,
    kb_retry_login,
    kb_retry_register,
    kb_unknown,
)

GUEST_HOME_TEXT = (
    "Привет! Я Postavleno_Bot 👋\n"
    "Помогаю работать с Wildberries и МойСклад.\n\n"
    "Чтобы продолжить, выберите действие ниже."
)

AUTH_HOME_TEMPLATE = (
    "Рада видеть вас, {name}! ✨\n\n"
    "Интеграции:\n"
    "• WB API: {wb}\n"
    "• МойСклад API: {ms}\n\n"
    "Профиль поможет обновить данные и запустить экспорт."
)

EXPORT_PROGRESS_TEXT = "Собираю данные…"
EXPORT_READY_TEMPLATE = "Готово ✅"
EXPORT_MISSING_TEMPLATE = "Добавьте ключи в профиле."
EXPORT_ERROR_TEXT = "Не удалось собрать файл. Попробуйте чуть позже."

REQUIRE_AUTH_TEXT = "Нужно авторизоваться. Выберите действие ниже."

LOGIN_TEXT = "🔑 Авторизация\n\nВведите логин."
LOGIN_PASSWORD_TEXT = "🔑 Авторизация\n\nЛогин принят. Введите пароль."
REGISTER_TEXT = (
    "🆕 Регистрация\n\n"
    "Придумайте логин: латиница, цифры, точка, дефис, подчёркивание (3–32)."
)
REGISTER_PASSWORD_TEXT = "🆕 Регистрация\n\nЛогин принят. Введите пароль (≥ 6 символов)."
EDIT_COMPANY_TEXT = "🏢 Смена названия компании\n\nВведите новое название (1–60 символов)."
EDIT_WB_TEXT = "🔑 Смена WB API\n\nОтправьте новый ключ."
EDIT_MS_TEXT = "🔑 Смена «Мой Склад» API\n\nОтправьте новый ключ."
EDIT_EMAIL_TEXT = "✉️ Смена почты\n\nСкоро появится подтверждение email."
LOGIN_ERROR_TEXT = "Аккаунт не найден."
REGISTER_TAKEN_TEXT = "Логин занят, придумайте другой."
UNKNOWN_TEXT = "Не понял запрос 🤔 Выберите действие ниже."

DELETE_CONFIRM_TEXT = (
    "Удалить аккаунт навсегда? Данные на диске будут стерты. Это действие нельзя отменить."
)

DELETE_ERROR_TEXT = "Не удалось удалить аккаунт. Попробуйте позже."


async def _apply_nav(state: FSMContext, action: str, screen: ScreenState) -> None:
    if action == "root":
        await nav_root(state, screen)
    elif action == "push":
        await nav_push(state, screen)
    else:
        await nav_replace(state, screen)


async def render_home(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "root",
    is_authed: bool = False,
    profile: AccountProfile | None = None,
    extra: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_HOME))
    if not is_authed or profile is None:
        text = GUEST_HOME_TEXT
        keyboard = kb_home(False)
    else:
        name = profile.company_name or profile.display_login
        text = AUTH_HOME_TEMPLATE.format(
            name=name,
            wb="✅" if profile.wb_api else "❌",
            ms="✅" if profile.ms_api else "❌",
        )
        if extra:
            text = f"{text}\n\n{extra}"
        keyboard = kb_home(True)
    return await card_manager.render(bot, chat_id, text, reply_markup=keyboard, state=state)


async def render_export_progress(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    kind: str,
    nav_action: str = "push",
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EXPORT_STATUS, {"kind": kind, "status": "progress"}),
    )
    return await card_manager.render(
        bot,
        chat_id,
        EXPORT_PROGRESS_TEXT,
        reply_markup=None,
        state=state,
    )


async def render_export_missing_token(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    service: str,
    nav_action: str = "push",
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EXPORT_STATUS, {"service": service, "status": "missing"}),
    )
    service_name = "МойСклад" if service.upper() == "MS" else "WB"
    text = f"Не хватает ключа {service_name}. {EXPORT_MISSING_TEMPLATE}"
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_export_missing_token(),
        state=state,
    )


async def render_export_error(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    kind: str,
    nav_action: str = "replace",
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EXPORT_STATUS, {"kind": kind, "status": "error"}),
    )
    return await card_manager.render(
        bot,
        chat_id,
        EXPORT_ERROR_TEXT,
        reply_markup=kb_export_error(),
        state=state,
    )


async def render_export_ready(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    kind: str,
    nav_action: str = "replace",
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EXPORT_DONE, {"kind": kind, "status": "done"}),
    )
    return await card_manager.render(
        bot,
        chat_id,
        EXPORT_READY_TEMPLATE,
        reply_markup=kb_export_ready(),
        state=state,
    )


async def render_delete_confirm(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_DELETE_CONFIRM))
    return await card_manager.render(
        bot,
        chat_id,
        DELETE_CONFIRM_TEXT,
        reply_markup=kb_delete_confirm(),
        state=state,
    )


async def render_delete_error(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "replace",
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_DELETE_CONFIRM, {"error": True}))
    return await card_manager.render(
        bot,
        chat_id,
        DELETE_ERROR_TEXT,
        reply_markup=kb_delete_error(),
        state=state,
    )


async def render_require_auth(
    bot: Bot, state: FSMContext, chat_id: int, *, nav_action: str = "replace"
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_AUTH_MENU))
    return await card_manager.render(
        bot,
        chat_id,
        REQUIRE_AUTH_TEXT,
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
    wb_state = "✅" if profile.wb_api else "❌"
    ms_state = "✅" if profile.ms_api else "❌"
    email = profile.email or "—"
    company = profile.company_name or profile.display_login
    lines = [
        "👤 Профиль",
        "",
        f"Компания: {company}",
        f"Логин: {profile.display_login}",
        f"Дата регистрации: {_format_datetime(profile.created_at)}",
        f"Почта: {email}",
        f"WB API: {wb_state}",
        f"МойСклад API: {ms_state}",
    ]
    if extra:
        lines.extend(["", extra])
    text = "\n".join(lines)
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_profile(), state=state)


async def render_edit_company(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    prompt: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_COMPANY))
    text = EDIT_COMPANY_TEXT if not prompt else f"{EDIT_COMPANY_TEXT}\n\n{prompt}"
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_edit_company(),
        state=state,
    )


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

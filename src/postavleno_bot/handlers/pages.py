"""Rendering helpers for bot screens."""

from __future__ import annotations

from datetime import datetime

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import User

from ..navigation import (
    SCREEN_AUTH_MENU,
    SCREEN_DELETE_CONFIRM,
    SCREEN_EDIT_COMPANY,
    SCREEN_EDIT_EMAIL,
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
    kb_company_delete_confirm,
    kb_company_menu,
    kb_delete_confirm,
    kb_delete_error,
    kb_edit_company,
    kb_edit_email,
    kb_edit_wb,
    kb_email_menu,
    kb_email_unlink_confirm,
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
    "Помогаю работать с Wildberries.\n\n"
    "Чтобы продолжить, выберите действие ниже."
)

AUTH_HOME_TEMPLATE = (
    "Привет, {tg_login}! ✨\n\n"
    "Интеграции:\n"
    "• WB API: {wb}"
)

PROFILE_HINT = "Профиль поможет обновить данные и запустить экспорт."

EXPORT_PROGRESS_TEXT = "Собираю данные…"
EXPORT_READY_TEMPLATE = "Готово ✅"
EXPORT_MISSING_TEMPLATE = "Добавьте ключи в профиле."
EXPORT_ERROR_TEMPLATE = (
    "Не получилось собрать файл 😕 Проверьте ключ {service} в профиле и попробуйте ещё раз."
)

REQUIRE_AUTH_TEXT = "Нужно авторизоваться. Выберите действие ниже."

LOGIN_TEXT = "🔑 Авторизация\n\nВведите логин."
LOGIN_PASSWORD_TEXT = "🔑 Авторизация\n\nЛогин принят. Введите пароль."
REGISTER_TEXT = (
    "🆕 Регистрация\n\n"
    "Придумайте логин: латиница, цифры, точка, дефис, подчёркивание (3–32)."
)
REGISTER_PASSWORD_TEXT = "🆕 Регистрация\n\nЛогин принят. Введите пароль (≥ 6 символов)."
COMPANY_REQUEST_TEXT = (
    "Давайте укажем название вашей компании. Отправьте одно сообщением название (до 70 символов)."
)
COMPANY_RENAME_TEXT = (
    "✏️ Переименовать компанию\n\n"
    "Отправьте новое название (до 70 символов)."
)
COMPANY_MENU_TEMPLATE = (
    "🏢 Компания\n\n"
    "Текущее название: {company}"
)
COMPANY_DELETE_CONFIRM_TEXT = "Вы уверены? Да/Нет"
EDIT_WB_TEXT = (
    "🔑 WB API\n\n"
    "Отправьте ваш WB API ключ одним сообщением. Его можно сгенерировать в кабинете WB."
)
EMAIL_REQUEST_TEXT = (
    "✉️ Почта\n\n"
    "Укажите адрес электронной почты одним сообщением (пример: name@domain.com). Мы отправим код подтверждения."
)
EMAIL_CODE_TEXT = (
    "✉️ Почта\n\n"
    "Мы отправили код на {email}. Введите код одним сообщением. Отменить — /cancel."
)
EMAIL_UNLINK_TEXT = "Отвязать почту? Вы уверены?"
EMAIL_MENU_TEMPLATE = (
    "✉️ Почта\n\n"
    "Текущий адрес: {email}\n"
    "Статус: {status}"
)
LOGIN_ERROR_TEXT = "Аккаунт не найден."
REGISTER_TAKEN_TEXT = "Логин занят, придумайте другой."
UNKNOWN_TEXT = "Не понял запрос 🤔"

DELETE_CONFIRM_TEXT = (
    "Вы уверены, что хотите удалить аккаунт? Действие необратимо. Да/Нет"
)

DELETE_ERROR_TEXT = "Не удалось удалить аккаунт. Попробуйте позже."


async def _apply_nav(state: FSMContext, action: str, screen: ScreenState) -> None:
    if action == "root":
        await nav_root(state, screen)
    elif action == "push":
        await nav_push(state, screen)
    else:
        await nav_replace(state, screen)


def _resolve_home_name(profile: AccountProfile | None, tg_user: User | None) -> str:
    if tg_user:
        username = (tg_user.username or "").strip()
        if username:
            return f"@{username}"
        first_name = (tg_user.first_name or "").strip()
        if first_name:
            return first_name
    if profile:
        return profile.display_login
    return "друг"


async def render_home(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "root",
    is_authed: bool = False,
    profile: AccountProfile | None = None,
    tg_user: User | None = None,
    extra: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_HOME))
    if not is_authed or profile is None:
        text = "".join(GUEST_HOME_TEXT)
        keyboard = kb_home(False)
    else:
        name = _resolve_home_name(profile, tg_user)
        text = "".join(
            [
                AUTH_HOME_TEMPLATE.format(
                    tg_login=name,
                    wb="✅" if profile.wb_api else "❌",
                ),
                "\n\n",
                PROFILE_HINT,
            ]
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
    service_name = "WB" if service.upper() == "WB" else service.upper()
    text = f"Не хватает ключа {service_name}. {EXPORT_MISSING_TEMPLATE}"
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_export_missing_token(),
        state=state,
    )


def _service_name_from_kind(kind: str) -> str:
    return "WB"


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
    text = EXPORT_ERROR_TEMPLATE.format(service=_service_name_from_kind(kind))
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_export_error(), state=state)


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
    if profile.email:
        status = "подтверждена ✅" if profile.email_verified else "не подтверждена ❌"
        email_line = f"{profile.email} ({status})"
    else:
        email_line = "—"
    company = profile.company_name.strip() if profile.company_name else ""
    if not company:
        company = "—"
    lines = [
        f"👤 Профиль: {profile.display_login}",
        f"Компания: {company}",
        f"Дата регистрации: {_format_datetime(profile.created_at)}",
        f"Почта: {email_line}",
        f"WB API: {wb_state}",
        "",
        PROFILE_HINT,
    ]
    if extra:
        lines.extend(["", extra])
    text = "\n".join(lines)
    return await card_manager.render(bot, chat_id, text, reply_markup=kb_profile(), state=state)


async def render_company_menu(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    profile: AccountProfile,
    nav_action: str = "push",
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_COMPANY, {"mode": "menu"}))
    company = profile.company_name.strip() if profile.company_name else ""
    if not company:
        company = "—"
    text = COMPANY_MENU_TEMPLATE.format(company=company)
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_company_menu(),
        state=state,
    )


async def render_company_prompt(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    rename: bool = False,
    prompt: str | None = None,
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EDIT_COMPANY, {"mode": "prompt", "rename": rename}),
    )
    base = COMPANY_RENAME_TEXT if rename else COMPANY_REQUEST_TEXT
    text = base if not prompt else f"{base}\n\n{prompt}"
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


async def render_company_delete_confirm(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    prompt: str | None = None,
) -> int:
    await _apply_nav(
        state,
        nav_action,
        ScreenState(SCREEN_EDIT_COMPANY, {"mode": "delete"}),
    )
    text = COMPANY_DELETE_CONFIRM_TEXT if not prompt else f"{COMPANY_DELETE_CONFIRM_TEXT}\n\n{prompt}"
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_company_delete_confirm(),
        state=state,
    )


async def render_edit_email(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    await_code: bool = False,
    email: str | None = None,
    prompt: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_EMAIL))
    base = EMAIL_CODE_TEXT.format(email=email or "указанный адрес") if await_code else EMAIL_REQUEST_TEXT
    if prompt:
        base = f"{base}\n\n{prompt}"
    return await card_manager.render(bot, chat_id, base, reply_markup=kb_edit_email(), state=state)


async def render_email_menu(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    profile: AccountProfile,
    nav_action: str = "push",
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_EMAIL, {"mode": "menu"}))
    email = profile.email or "—"
    status = "подтверждена ✅" if profile.email_verified else "не подтверждена ❌"
    text = EMAIL_MENU_TEMPLATE.format(email=email, status=status)
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_email_menu(),
        state=state,
    )


async def render_email_unlink_confirm(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    *,
    nav_action: str = "push",
    prompt: str | None = None,
) -> int:
    await _apply_nav(state, nav_action, ScreenState(SCREEN_EDIT_EMAIL, {"mode": "unlink"}))
    text = EMAIL_UNLINK_TEXT if not prompt else f"{EMAIL_UNLINK_TEXT}\n\n{prompt}"
    return await card_manager.render(
        bot,
        chat_id,
        text,
        reply_markup=kb_email_unlink_confirm(),
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

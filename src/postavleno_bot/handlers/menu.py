from __future__ import annotations

import re
import time
from typing import cast

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from structlog.stdlib import BoundLogger

from ..core.crypto import SecretKeyError, decrypt_str
from ..core.logging import get_logger
from ..db.engine import session_scope
from ..db.models import User
from ..db.repo import TokenKind, UserRepository
from ..state.session import (
    ChatSession,
    ScreenState,
    nav_back,
    nav_push,
    nav_replace,
    session_storage,
)
from ..utils.safe_telegram import safe_delete, safe_edit, safe_send
from ..utils.strings import format_datetime, mask_secret

MENU_ROUTER = Router(name="menu")

SCREEN_MAIN = "MAIN"
SCREEN_AUTH = "AUTH"
SCREEN_PROFILE = "PROFILE"

CALLBACK_MAIN_REFRESH = "main.refresh"
CALLBACK_MAIN_AUTH = "main.auth"
CALLBACK_MAIN_EXIT = "main.exit"
CALLBACK_REFRESH = "screen.refresh"
CALLBACK_BACK = "nav.back"
CALLBACK_PROFILE_NAME = "profile.name"
CALLBACK_PROFILE_COMPANY = "profile.company"
CALLBACK_PROFILE_TG = "profile.tg"
CALLBACK_PROFILE_WB = "profile.wb"
CALLBACK_PROFILE_MS = "profile.ms"

TOKEN_ORDER: tuple[TokenKind, ...] = ("tg_bot", "wb_api", "moysklad")
TOKEN_ATTRS: dict[TokenKind, str] = {
    "tg_bot": "tg_bot_token_enc",
    "wb_api": "wb_api_token_enc",
    "moysklad": "moysklad_api_token_enc",
}
TOKEN_STEP_MESSAGES: dict[TokenKind, str] = {
    "tg_bot": "TG BOT — отправьте токен бота Telegram (формат 1234567890:AA...).",
    "wb_api": "API WB — затем отправьте ключ Wildberries.",
    "moysklad": "API «МойСклад» — затем отправьте ключ МойСклад.",
}
TOKEN_EXPECTATIONS: dict[TokenKind, str] = {
    "tg_bot": "TG BOT",
    "wb_api": "API WB",
    "moysklad": "API «МойСклад»",
}
TOKEN_PROFILE_LABELS: dict[TokenKind, str] = {
    "tg_bot": "TG BOT",
    "wb_api": "WB API",
    "moysklad": "МойСклад API",
}
TOKEN_PATTERNS = {
    "tg_bot": re.compile(r"^\d+:[A-Za-z0-9_-]{35,}$"),
    "wb_api": re.compile(r"^[A-Za-z0-9]{32,128}$"),
    "moysklad_basic": re.compile(r"^Basic\s+\S+$", re.IGNORECASE),
    "moysklad_token": re.compile(r"^[A-Za-z0-9_\-]{8,128}$"),
}
TOKEN_ERROR_TEXT = {
    "tg_bot": "Не похоже на токен бота Telegram. Формат: 1234567890:AA...",
    "wb_api": "Токен WB должен содержать 32–128 символов латиницы и цифр.",
    "moysklad": (
        "Ключ «МойСклад» должен быть в формате Basic base64(user:pass) или содержать "
        "8–128 символов латиницы, цифр, -, _."
    ),
}
PROFILE_PROMPTS = {
    "name": "Пришлите новое имя.",
    "company": "Пришлите новое название компании.",
    "tg_bot": "Пришлите новый токен бота Telegram.",
    "wb_api": "Пришлите новый ключ Wildberries.",
    "moysklad": "Пришлите новый ключ «МойСклад».",
}
TOKEN_SUCCESS_MESSAGES = {
    "tg_bot": "Ключ TG BOT сохранён ✅",
    "wb_api": "Ключ WB сохранён ✅",
    "moysklad": "Ключ «МойСклад» сохранён ✅",
}


def _calc_latency(started_at: float | None) -> float | None:
    if started_at is None:
        return None
    return (time.perf_counter() - started_at) * 1000


def _bind_logger(action: str, request_id: str | None = None) -> BoundLogger:
    logger = get_logger(__name__).bind(action=action)
    if request_id:
        logger = logger.bind(request_id=request_id)
    return logger


def _apply_nav(session: ChatSession, screen: ScreenState, *, nav_action: str) -> None:
    if nav_action == "root":
        session.history = [screen]
    elif nav_action == "push":
        nav_push(session, screen)
    else:
        nav_replace(session, screen)


def _next_missing_token(user: User) -> TokenKind | None:
    for kind in TOKEN_ORDER:
        attr = TOKEN_ATTRS[kind]
        if getattr(user, attr) is None:
            return kind
    return None


def _current_screen(session: ChatSession) -> ScreenState | None:
    if not session.history:
        return None
    return session.history[-1]


def _get_token_plain(user: User, kind: TokenKind) -> str | None:
    attr = TOKEN_ATTRS[kind]
    encrypted = getattr(user, attr)
    if encrypted is None:
        return None
    try:
        return decrypt_str(encrypted)
    except SecretKeyError:
        logger = get_logger(__name__).bind(action="token.decrypt", kind=kind)
        logger.error("Не удалось расшифровать токен", outcome="fail")
        return None


def _build_main_text() -> str:
    return (
        "Привет! 👋 Я Postavleno_Bot.\n\n"
        "Совсем скоро здесь появятся удобные инструменты для работы с Wildberries и МойСклад: "
        "отчёты, сверки и быстрые действия — всё в одном окне.\n\n"
        "Чтобы подготовиться к запуску, подключите ваши ключи доступа — нажмите «🔐 Авторизация»."
    )


def _build_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Авторизация", callback_data=CALLBACK_MAIN_AUTH)],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_MAIN_REFRESH),
                InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT),
            ],
        ]
    )


async def _show_message(
    bot: Bot,
    chat_id: int,
    text: str,
    keyboard: InlineKeyboardMarkup | None,
) -> int | None:
    last_id = await session_storage.get_last_message_id(chat_id)
    if last_id is None:
        message = await safe_send(bot, chat_id=chat_id, text=text, reply_markup=keyboard)
    else:
        message = await safe_edit(
            bot,
            chat_id=chat_id,
            message_id=last_id,
            text=text,
            inline_markup=keyboard,
        )
        if message is None:
            message = await safe_send(bot, chat_id=chat_id, text=text, reply_markup=keyboard)
    if message:
        await session_storage.set_last_message_id(chat_id, message.message_id)
        return message.message_id
    return None


async def _render_main(bot: Bot, chat_id: int, *, nav_action: str = "root") -> int | None:
    session = await session_storage.get_session(chat_id)
    session.pending_input = None
    _apply_nav(session, ScreenState(name=SCREEN_MAIN), nav_action=nav_action)
    return await _show_message(bot, chat_id, _build_main_text(), _build_main_keyboard())


async def _render_auth(
    bot: Bot,
    chat_id: int,
    user: User,
    *,
    nav_action: str = "replace",
) -> int | None:
    session = await session_storage.get_session(chat_id)
    _apply_nav(session, ScreenState(name=SCREEN_AUTH), nav_action=nav_action)
    next_token = _next_missing_token(user)
    session.pending_input = f"auth:{next_token}" if next_token else None

    steps: list[str] = []
    for kind in TOKEN_ORDER:
        has_token = getattr(user, TOKEN_ATTRS[kind]) is not None
        prefix = "✅" if has_token else "⬜"
        steps.append(f"{prefix} {TOKEN_STEP_MESSAGES[kind]}")

    lines = [
        "🔐 Авторизация",
        "",
        *steps,
        "",
        "Отправляйте ключи по очереди в ответ на это сообщение — я поставлю ✅ за каждый шаг.",
    ]
    if next_token:
        lines.extend(["", f"Сейчас ожидаю ключ: {TOKEN_EXPECTATIONS[next_token]}."])
    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_REFRESH)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_BACK)],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT)],
        ]
    )
    return await _show_message(bot, chat_id, text, keyboard)


async def _render_profile(
    bot: Bot,
    chat_id: int,
    user: User,
    *,
    nav_action: str = "replace",
    prompt: str | None = None,
    pending_input: str | None = None,
) -> int | None:
    session = await session_storage.get_session(chat_id)
    _apply_nav(session, ScreenState(name=SCREEN_PROFILE), nav_action=nav_action)
    session.pending_input = pending_input

    tokens_lines = [
        f"• {TOKEN_PROFILE_LABELS[kind]}: {mask_secret(_get_token_plain(user, kind))}"
        for kind in TOKEN_ORDER
    ]

    lines = [
        "👤 Профиль",
        "",
        f"Компания: {user.company_name or '—'}",
        f"Имя в боте: {user.display_name or '—'}",
        f"Дата регистрации: {format_datetime(user.registered_at)}",
        "",
        "Ключи доступа:",
        *tokens_lines,
    ]
    if prompt:
        lines.extend(["", prompt])

    text = "\n".join(lines)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Имя", callback_data=CALLBACK_PROFILE_NAME),
                InlineKeyboardButton(text="🏷️ Компания", callback_data=CALLBACK_PROFILE_COMPANY),
            ],
            [
                InlineKeyboardButton(text="🔑 TG BOT", callback_data=CALLBACK_PROFILE_TG),
                InlineKeyboardButton(text="🟣 WB API", callback_data=CALLBACK_PROFILE_WB),
                InlineKeyboardButton(text="🏭 МойСклад API", callback_data=CALLBACK_PROFILE_MS),
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_REFRESH),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_BACK),
                InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT),
            ],
        ]
    )
    return await _show_message(bot, chat_id, text, keyboard)


async def _ensure_user(
    *,
    tg_user_id: int,
    chat_id: int,
    username: str | None,
) -> User:
    async with session_scope() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(tg_user_id=tg_user_id, chat_id=chat_id, username=username)
        return user


async def _save_token(
    *,
    tg_user_id: int,
    chat_id: int,
    username: str | None,
    kind: TokenKind,
    token: str,
) -> User:
    async with session_scope() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(tg_user_id=tg_user_id, chat_id=chat_id, username=username)
        user = await repo.set_token(user, kind, token)
        return user


async def _update_display_name(
    *,
    tg_user_id: int,
    chat_id: int,
    username: str | None,
    display_name: str,
) -> User:
    async with session_scope() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(tg_user_id=tg_user_id, chat_id=chat_id, username=username)
        user = await repo.update_profile(user, display_name=display_name)
        return user


async def _update_company_name(
    *,
    tg_user_id: int,
    chat_id: int,
    username: str | None,
    company_name: str,
) -> User:
    async with session_scope() as session:
        repo = UserRepository(session)
        user = await repo.get_or_create(tg_user_id=tg_user_id, chat_id=chat_id, username=username)
        user = await repo.update_profile(user, company_name=company_name)
        return user


def _validate_token(kind: TokenKind, value: str) -> bool:
    if kind == "tg_bot":
        return bool(TOKEN_PATTERNS["tg_bot"].match(value))
    if kind == "wb_api":
        return bool(TOKEN_PATTERNS["wb_api"].match(value))
    if kind == "moysklad":
        return bool(
            TOKEN_PATTERNS["moysklad_basic"].match(value)
            or TOKEN_PATTERNS["moysklad_token"].match(value)
        )
    return False


def _build_token_error(kind: TokenKind) -> str:
    return TOKEN_ERROR_TEXT[kind]


async def _render_current(bot: Bot, chat_id: int, user: User) -> int | None:
    session = await session_storage.get_session(chat_id)
    current = _current_screen(session)
    if current is None:
        return await _render_main(bot, chat_id, nav_action="root")
    if current.name == SCREEN_MAIN:
        return await _render_main(bot, chat_id, nav_action="root")
    if current.name == SCREEN_AUTH:
        return await _render_auth(bot, chat_id, user, nav_action="replace")
    if current.name == SCREEN_PROFILE:
        return await _render_profile(bot, chat_id, user, nav_action="replace")
    return await _render_main(bot, chat_id, nav_action="root")


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    if message.from_user is None:
        return
    logger = _bind_logger("start", request_id)
    await _ensure_user(
        tg_user_id=message.from_user.id,
        chat_id=message.chat.id,
        username=message.from_user.username,
    )
    message_id = await _render_main(bot, message.chat.id, nav_action="root")
    latency = _calc_latency(started_at)
    logger.info("Главное меню открыто", outcome="ok", latency_ms=latency, message_id=message_id)


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_REFRESH)
async def handle_main_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = _bind_logger("main.refresh", request_id)
    await _ensure_user(
        tg_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
    )
    message_id = await _render_main(bot, callback.message.chat.id, nav_action="root")
    latency = _calc_latency(started_at)
    logger.info("Главный экран обновлён", outcome="ok", latency_ms=latency, message_id=message_id)


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_AUTH)
async def handle_main_auth(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = _bind_logger("auth.open", request_id)
    user = await _ensure_user(
        tg_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
    )
    if user.is_registered:
        message_id = await _render_profile(
            bot,
            callback.message.chat.id,
            user,
            nav_action="push",
        )
        action_name = "Профиль открыт"
    else:
        message_id = await _render_auth(
            bot,
            callback.message.chat.id,
            user,
            nav_action="push",
        )
        action_name = "Экран авторизации открыт"
    latency = _calc_latency(started_at)
    logger.info(action_name, outcome="ok", latency_ms=latency, message_id=message_id)


@MENU_ROUTER.callback_query(F.data == CALLBACK_REFRESH)
async def handle_screen_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = _bind_logger("screen.refresh", request_id)
    user = await _ensure_user(
        tg_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
    )
    message_id = await _render_current(bot, callback.message.chat.id, user)
    latency = _calc_latency(started_at)
    logger.info("Экран обновлён", outcome="ok", latency_ms=latency, message_id=message_id)


@MENU_ROUTER.callback_query(F.data == CALLBACK_BACK)
async def handle_back(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = _bind_logger("nav.back", request_id)
    chat_id = callback.message.chat.id
    session = await session_storage.get_session(chat_id)
    nav_back(session)
    user = await _ensure_user(
        tg_user_id=callback.from_user.id,
        chat_id=chat_id,
        username=callback.from_user.username,
    )
    message_id = await _render_current(bot, chat_id, user)
    latency = _calc_latency(started_at)
    logger.info(
        "Возврат на предыдущий экран", outcome="ok", latency_ms=latency, message_id=message_id
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_EXIT)
async def handle_exit(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = _bind_logger("exit", request_id)
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    await safe_delete(bot, chat_id=chat_id, message_id=message_id)
    await session_storage.clear(chat_id)
    latency = _calc_latency(started_at)
    logger.info("Меню закрыто", outcome="ok", latency_ms=latency)


async def _open_profile_editor(
    callback: CallbackQuery,
    bot: Bot,
    request_id: str,
    started_at: float,
    target: str,
    *,
    pending_value: str,
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = _bind_logger(f"profile.edit.{target}", request_id)
    user = await _ensure_user(
        tg_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        username=callback.from_user.username,
    )
    prompt = PROFILE_PROMPTS[pending_value]
    message_id = await _render_profile(
        bot,
        callback.message.chat.id,
        user,
        nav_action="replace",
        prompt=prompt,
        pending_input=f"profile:{pending_value}",
    )
    latency = _calc_latency(started_at)
    logger.info(
        "Запрошено обновление профиля", outcome="ok", latency_ms=latency, message_id=message_id
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_NAME)
async def handle_profile_name(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    await _open_profile_editor(
        callback,
        bot,
        request_id,
        started_at,
        "name",
        pending_value="name",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_COMPANY)
async def handle_profile_company(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    await _open_profile_editor(
        callback,
        bot,
        request_id,
        started_at,
        "company",
        pending_value="company",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_TG)
async def handle_profile_tg(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    await _open_profile_editor(
        callback,
        bot,
        request_id,
        started_at,
        "tg",
        pending_value="tg_bot",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_WB)
async def handle_profile_wb(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    await _open_profile_editor(
        callback,
        bot,
        request_id,
        started_at,
        "wb",
        pending_value="wb_api",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_MS)
async def handle_profile_ms(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    await _open_profile_editor(
        callback,
        bot,
        request_id,
        started_at,
        "ms",
        pending_value="moysklad",
    )


@MENU_ROUTER.message(F.text)
async def handle_text_input(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    if message.from_user is None:
        return
    chat_id = message.chat.id
    session = await session_storage.get_session(chat_id)
    pending = session.pending_input
    if not pending:
        return
    logger = _bind_logger("input", request_id).bind(context=pending)
    action, _, target = pending.partition(":")
    raw_text = message.text or ""
    value = raw_text.strip()
    user_id = message.from_user.id
    username = message.from_user.username

    if action == "auth" and target in TOKEN_ATTRS:
        kind = cast(TokenKind, target)
        if not _validate_token(kind, value):
            await message.answer(_build_token_error(kind))
            logger.info("Невалидный токен", outcome="fail", kind=kind)
            return
        user = await _save_token(
            tg_user_id=user_id,
            chat_id=chat_id,
            username=username,
            kind=kind,
            token=value,
        )
        masked = mask_secret(value)
        await message.answer(f"{TOKEN_SUCCESS_MESSAGES[kind]} {masked}")
        logger.info("Токен сохранён", outcome="ok", kind=kind, mask=masked)
        if user.is_registered and _next_missing_token(user) is None:
            await _render_profile(bot, chat_id, user, nav_action="replace")
        else:
            await _render_auth(bot, chat_id, user, nav_action="replace")
        return

    if action == "profile":
        if target == "name":
            if not value:
                await message.answer("Имя не может быть пустым. Попробуйте ещё раз.")
                logger.info("Пустое имя", outcome="fail")
                return
            user = await _update_display_name(
                tg_user_id=user_id,
                chat_id=chat_id,
                username=username,
                display_name=value,
            )
            await message.answer("Имя обновлено ✅")
            logger.info("Имя обновлено", outcome="ok")
            await _render_profile(bot, chat_id, user, nav_action="replace")
            return
        if target == "company":
            if not value:
                await message.answer("Название компании не может быть пустым. Попробуйте ещё раз.")
                logger.info("Пустая компания", outcome="fail")
                return
            user = await _update_company_name(
                tg_user_id=user_id,
                chat_id=chat_id,
                username=username,
                company_name=value,
            )
            await message.answer("Компания обновлена ✅")
            logger.info("Компания обновлена", outcome="ok")
            await _render_profile(bot, chat_id, user, nav_action="replace")
            return
        if target in TOKEN_ATTRS:
            kind = cast(TokenKind, target)
            if not _validate_token(kind, value):
                await message.answer(_build_token_error(kind))
                logger.info("Невалидный токен", outcome="fail", kind=kind)
                return
            user = await _save_token(
                tg_user_id=user_id,
                chat_id=chat_id,
                username=username,
                kind=kind,
                token=value,
            )
            masked = mask_secret(value)
            await message.answer(f"{TOKEN_SUCCESS_MESSAGES[kind]} {masked}")
            logger.info("Токен обновлён", outcome="ok", kind=kind, mask=masked)
            await _render_profile(bot, chat_id, user, nav_action="replace")
            return

    logger.info("Неизвестный контекст ввода", outcome="fail")


__all__ = ["MENU_ROUTER"]

from __future__ import annotations

import io
import re
import time
from collections.abc import Iterable

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
)
from PIL import Image

from ..core.logging import get_logger
from ..services.users import (
    FileUserStorage,
    InvalidCredentialsError,
    LoginAlreadyExistsError,
    LoginNotFoundError,
    LoginOwnershipError,
    UserData,
    get_user_storage,
)
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

SCREEN_MAIN = "main"
SCREEN_AUTH = "auth"
SCREEN_PROFILE = "profile"

CALLBACK_MAIN_REFRESH = "main.refresh"
CALLBACK_MAIN_AUTH = "main.auth"
CALLBACK_MAIN_EXIT = "main.exit"
CALLBACK_AUTH_LOGIN = "auth.login"
CALLBACK_AUTH_REGISTER = "auth.register"
CALLBACK_AUTH_REFRESH = "auth.refresh"
CALLBACK_BACK = "nav.back"
CALLBACK_PROFILE_REFRESH = "profile.refresh"
CALLBACK_PROFILE_AVATAR = "profile.avatar"
CALLBACK_PROFILE_COMPANY = "profile.company"
CALLBACK_PROFILE_WB = "profile.wb"
CALLBACK_PROFILE_MS = "profile.ms"
CALLBACK_PROFILE_EMAIL = "profile.email"
CALLBACK_PROFILE_LOGOUT = "profile.logout"

RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_WINDOW = 600.0

LOGIN_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")
PASSWORD_MIN_LENGTH = 6
WB_PATTERN = re.compile(r"^[A-Za-z0-9]{32,128}$")
MS_PATTERN_TOKEN = re.compile(r"^[A-Za-z0-9_\-]{8,128}$")
MS_PATTERN_BASIC = re.compile(r"^Basic\s+\S+$", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _calc_latency(started_at: float | None) -> float | None:
    if started_at is None:
        return None
    return (time.perf_counter() - started_at) * 1000


def _apply_nav(session: ChatSession, screen: ScreenState, *, nav_action: str) -> None:
    if nav_action == "root":
        session.history = [screen]
    elif nav_action == "push":
        nav_push(session, screen)
    else:
        nav_replace(session, screen)


def _current_screen(session: ChatSession) -> ScreenState | None:
    if not session.history:
        return None
    return session.history[-1]


def _format_telegram_name(message: Message | CallbackQuery) -> str:
    from_user = message.from_user
    if from_user is None:
        return "—"
    parts: list[str] = []
    if from_user.first_name:
        parts.append(from_user.first_name)
    if from_user.last_name:
        parts.append(from_user.last_name)
    if not parts and from_user.username:
        parts.append(f"@{from_user.username}")
    if not parts:
        parts.append(str(from_user.id))
    return " ".join(parts)


def _build_main_text() -> str:
    return (
        "Привет! 👋 Я Postavleno_Bot.\n\n"
        "Скоро здесь появятся инструменты для работы с Wildberries и МойСклад —\n"
        "отчёты, сверки и быстрые действия в одном окне.\n\n"
        "Чтобы подготовиться к запуску, подключите аккаунт — нажмите «🔐 Авторизация»."
    )


def _build_main_keyboard(session: ChatSession) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if session.authorized_login is None:
        rows.append([InlineKeyboardButton(text="🔐 Авторизация", callback_data=CALLBACK_MAIN_AUTH)])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_MAIN_REFRESH)])
    rows.append([InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_auth_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Авторизация", callback_data=CALLBACK_AUTH_LOGIN)],
            [InlineKeyboardButton(text="Регистрация", callback_data=CALLBACK_AUTH_REGISTER)],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_AUTH_REFRESH)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_BACK)],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT)],
        ]
    )


def _build_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🖼️ Сменить Аватар", callback_data=CALLBACK_PROFILE_AVATAR)],
            [
                InlineKeyboardButton(
                    text="🏢 Сменить Компанию", callback_data=CALLBACK_PROFILE_COMPANY
                )
            ],
            [
                InlineKeyboardButton(text="🟣 Сменить WB API", callback_data=CALLBACK_PROFILE_WB),
                InlineKeyboardButton(
                    text="🏭 Сменить „МойСклад“ API", callback_data=CALLBACK_PROFILE_MS
                ),
            ],
            [InlineKeyboardButton(text="✉️ Сменить Почту", callback_data=CALLBACK_PROFILE_EMAIL)],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=CALLBACK_PROFILE_REFRESH)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_BACK)],
            [
                InlineKeyboardButton(
                    text="🚪 Выйти с профиля", callback_data=CALLBACK_PROFILE_LOGOUT
                )
            ],
            [InlineKeyboardButton(text="🚪 Выйти", callback_data=CALLBACK_MAIN_EXIT)],
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
    session.temp.clear()
    _apply_nav(session, ScreenState(name=SCREEN_MAIN), nav_action=nav_action)
    return await _show_message(bot, chat_id, _build_main_text(), _build_main_keyboard(session))


async def _render_auth(
    bot: Bot,
    chat_id: int,
    *,
    nav_action: str = "replace",
    prompt: str | None = None,
) -> int | None:
    session = await session_storage.get_session(chat_id)
    _apply_nav(session, ScreenState(name=SCREEN_AUTH), nav_action=nav_action)
    lines = [
        "🔐 Авторизация",
        "",
        "Вы можете войти в существующий аккаунт или создать новый.",
        "",
        "• Авторизация — введите логин и пароль.",
        "• Регистрация — придумайте логин и пароль.",
        "",
        "Логин: латиница, цифры, точка, дефис, подчёркивание (3–32 символа).",
        "Пароль: минимум 6 символов.",
    ]
    if prompt:
        lines.extend(["", prompt])
    text = "\n".join(lines)
    return await _show_message(bot, chat_id, text, _build_auth_keyboard())


def _format_profile_text(user: UserData) -> str:
    lines = [
        "👤 Профиль",
        "",
        f"Логин: {user.profile.login}",
        f"Компания: {user.profile.company or '—'}",
        f"Имя в TG: {user.profile.tg_name or '—'}",
        f"Дата регистрации: {format_datetime(user.profile.registered_at)}",
        "",
        f"Почта: {user.profile.email or '—'}",
        "",
        "Ключи:",
        f"• WB API: {mask_secret(user.secrets.wb_api)}",
        f"• МойСклад API: {mask_secret(user.secrets.ms_api)}",
    ]
    return "\n".join(lines)


async def _render_profile(
    bot: Bot,
    chat_id: int,
    user: UserData,
    *,
    nav_action: str = "replace",
    prompt: str | None = None,
    pending_input: str | None = None,
) -> int | None:
    session = await session_storage.get_session(chat_id)
    session.pending_input = pending_input
    _apply_nav(session, ScreenState(name=SCREEN_PROFILE), nav_action=nav_action)
    text = _format_profile_text(user)
    if prompt:
        text = f"{text}\n\n{prompt}"
    return await _show_message(bot, chat_id, text, _build_profile_keyboard())


def _get_storage() -> FileUserStorage:
    return get_user_storage()


async def _load_authorized_user(chat_id: int) -> UserData | None:
    session = await session_storage.get_session(chat_id)
    if not session.authorized_login:
        return None
    storage = _get_storage()
    try:
        return await storage.load_user(session.authorized_login)
    except LoginNotFoundError:
        session.authorized_login = None
        return None


def _prune_attempts(attempts: Iterable[float]) -> list[float]:
    now = time.monotonic()
    return [ts for ts in attempts if now - ts <= RATE_LIMIT_WINDOW]


def _allow_attempt(session: ChatSession) -> bool:
    cleaned = _prune_attempts(session.login_attempts)
    session.login_attempts.clear()
    session.login_attempts.extend(cleaned)
    if len(session.login_attempts) >= RATE_LIMIT_ATTEMPTS:
        return False
    session.login_attempts.append(time.monotonic())
    return True


def _mask_for_log(value: str | None) -> str:
    masked = mask_secret(value)
    if masked == "—":
        return masked
    return f"{masked} ({len(value or '')} chars)"


@MENU_ROUTER.message(Command("start"))
async def handle_start(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    if message.from_user is None:
        return
    logger = get_logger(__name__).bind(action="start", request_id=request_id)
    session = await session_storage.get_session(message.chat.id)
    if session.authorized_login:
        user = await _load_authorized_user(message.chat.id)
        if user:
            message_id = await _render_profile(bot, message.chat.id, user, nav_action="root")
            latency = _calc_latency(started_at)
            logger.info("Профиль открыт", outcome="ok", message_id=message_id, latency_ms=latency)
            return
        session.authorized_login = None
    message_id = await _render_main(bot, message.chat.id, nav_action="root")
    latency = _calc_latency(started_at)
    logger.info("Главное меню открыто", outcome="ok", message_id=message_id, latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_REFRESH)
async def handle_main_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="main.refresh", request_id=request_id)
    user = await _load_authorized_user(callback.message.chat.id)
    if user:
        message_id = await _render_profile(
            bot, callback.message.chat.id, user, nav_action="replace"
        )
    else:
        message_id = await _render_main(bot, callback.message.chat.id, nav_action="root")
    latency = _calc_latency(started_at)
    logger.info("Главный экран обновлён", outcome="ok", message_id=message_id, latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_AUTH)
async def handle_main_auth(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="auth.open", request_id=request_id)
    session = await session_storage.get_session(callback.message.chat.id)
    session.pending_input = None
    session.temp.clear()
    message_id = await _render_auth(bot, callback.message.chat.id, nav_action="push")
    latency = _calc_latency(started_at)
    logger.info("Экран авторизации открыт", outcome="ok", message_id=message_id, latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_AUTH_REFRESH)
async def handle_auth_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="auth.refresh", request_id=request_id)
    session = await session_storage.get_session(callback.message.chat.id)
    session.pending_input = None
    session.temp.clear()
    message_id = await _render_auth(bot, callback.message.chat.id, nav_action="replace")
    latency = _calc_latency(started_at)
    logger.info(
        "Экран авторизации обновлён", outcome="ok", message_id=message_id, latency_ms=latency
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_BACK)
async def handle_back(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="nav.back", request_id=request_id)
    session = await session_storage.get_session(callback.message.chat.id)
    session.pending_input = None
    session.temp.clear()
    nav_back(session)
    current = _current_screen(session)
    if current is None or current.name == SCREEN_MAIN:
        message_id = await _render_main(bot, callback.message.chat.id, nav_action="root")
    elif current.name == SCREEN_AUTH:
        message_id = await _render_auth(bot, callback.message.chat.id, nav_action="replace")
    elif current.name == SCREEN_PROFILE:
        user = await _load_authorized_user(callback.message.chat.id)
        if user:
            message_id = await _render_profile(
                bot, callback.message.chat.id, user, nav_action="replace"
            )
        else:
            message_id = await _render_main(bot, callback.message.chat.id, nav_action="root")
    else:
        message_id = await _render_main(bot, callback.message.chat.id, nav_action="root")
    latency = _calc_latency(started_at)
    logger.info(
        "Возврат на предыдущий экран", outcome="ok", message_id=message_id, latency_ms=latency
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_MAIN_EXIT)
async def handle_exit(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="exit", request_id=request_id)
    chat_id = callback.message.chat.id
    await safe_delete(bot, chat_id=chat_id, message_id=callback.message.message_id)
    await session_storage.clear(chat_id)
    latency = _calc_latency(started_at)
    logger.info("Меню закрыто", outcome="ok", latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_AUTH_REGISTER)
async def handle_register(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="register.start", request_id=request_id)
    session = await session_storage.get_session(callback.message.chat.id)
    session.pending_input = "register:login"
    session.temp.clear()
    prompt = "Придумайте логин: латиница, цифры, точка, дефис, подчёркивание (3–32)."
    message_id = await _render_auth(
        bot, callback.message.chat.id, nav_action="replace", prompt=prompt
    )
    latency = _calc_latency(started_at)
    logger.info("Регистрация запущена", outcome="ok", message_id=message_id, latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_AUTH_LOGIN)
async def handle_login(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None or callback.from_user is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="login.start", request_id=request_id)
    session = await session_storage.get_session(callback.message.chat.id)
    session.pending_input = "login:login"
    session.temp.clear()
    prompt = "Введите логин, который вы использовали при регистрации."
    message_id = await _render_auth(
        bot, callback.message.chat.id, nav_action="replace", prompt=prompt
    )
    latency = _calc_latency(started_at)
    logger.info("Авторизация запущена", outcome="ok", message_id=message_id, latency_ms=latency)


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_REFRESH)
async def handle_profile_refresh(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    logger = get_logger(__name__).bind(action="profile.refresh", request_id=request_id)
    user = await _load_authorized_user(callback.message.chat.id)
    if user is None:
        message_id = await _render_auth(bot, callback.message.chat.id, nav_action="replace")
        logger.warning("Профиль недоступен", outcome="fail", reason="not_authorized")
    else:
        message_id = await _render_profile(
            bot, callback.message.chat.id, user, nav_action="replace"
        )
    latency = _calc_latency(started_at)
    logger.info("Профиль обновлён", outcome="ok", message_id=message_id, latency_ms=latency)


async def _require_authorized_profile(
    callback: CallbackQuery,
    *,
    request_id: str,
) -> tuple[UserData | None, ChatSession | None]:
    if callback.message is None:
        return None, None
    session = await session_storage.get_session(callback.message.chat.id)
    if not session.authorized_login:
        await callback.answer("Сначала авторизуйтесь", show_alert=True)
        return None, None
    storage = _get_storage()
    try:
        user = await storage.load_user(session.authorized_login)
    except LoginNotFoundError:
        session.authorized_login = None
        await callback.answer("Аккаунт не найден. Зарегистрируйтесь заново.", show_alert=True)
        return None, session
    return user, session


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_LOGOUT)
async def handle_profile_logout(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    session = await session_storage.get_session(callback.message.chat.id)
    session.authorized_login = None
    session.pending_input = None
    session.temp.clear()
    session.login_attempts.clear()
    logger = get_logger(__name__).bind(action="profile.logout", request_id=request_id)
    prompt = "Вы вышли из профиля. Чтобы войти снова, используйте кнопки ниже."
    message_id = await _render_auth(
        bot, callback.message.chat.id, nav_action="replace", prompt=prompt
    )
    latency = _calc_latency(started_at)
    logger.info(
        "Пользователь вышел из профиля", outcome="ok", message_id=message_id, latency_ms=latency
    )


async def _prompt_profile_edit(
    callback: CallbackQuery,
    bot: Bot,
    *,
    session: ChatSession,
    user: UserData,
    prompt: str,
    pending_input: str,
) -> None:
    message = callback.message
    if message is None:
        return
    session.pending_input = pending_input
    await _render_profile(
        bot,
        message.chat.id,
        user,
        nav_action="replace",
        prompt=prompt,
        pending_input=pending_input,
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_COMPANY)
async def handle_profile_company(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    user, session = await _require_authorized_profile(callback, request_id=request_id)
    if not user or not session:
        return
    prompt = "Пришлите новое название компании (до 64 символов)."
    await _prompt_profile_edit(
        callback,
        bot,
        session=session,
        user=user,
        prompt=prompt,
        pending_input="profile:company",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_EMAIL)
async def handle_profile_email(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    user, session = await _require_authorized_profile(callback, request_id=request_id)
    if not user or not session:
        return
    prompt = "Укажите почту для уведомлений. Пример: name@example.com"
    await _prompt_profile_edit(
        callback,
        bot,
        session=session,
        user=user,
        prompt=prompt,
        pending_input="profile:email",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_WB)
async def handle_profile_wb(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    user, session = await _require_authorized_profile(callback, request_id=request_id)
    if not user or not session:
        return
    prompt = "Пришлите ключ WB API (32–128 символов латиницы и цифр)."
    await _prompt_profile_edit(
        callback,
        bot,
        session=session,
        user=user,
        prompt=prompt,
        pending_input="profile:wb",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_MS)
async def handle_profile_ms(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    user, session = await _require_authorized_profile(callback, request_id=request_id)
    if not user or not session:
        return
    prompt = "Пришлите ключ «МойСклад» (Basic ... или 8–128 символов)."
    await _prompt_profile_edit(
        callback,
        bot,
        session=session,
        user=user,
        prompt=prompt,
        pending_input="profile:ms",
    )


@MENU_ROUTER.callback_query(F.data == CALLBACK_PROFILE_AVATAR)
async def handle_profile_avatar(
    callback: CallbackQuery, bot: Bot, request_id: str, started_at: float
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    user, session = await _require_authorized_profile(callback, request_id=request_id)
    if not user or not session:
        return
    prompt = "Пришлите изображение (фото или файл) — я обрежу и сохраню как аватар."
    await _prompt_profile_edit(
        callback,
        bot,
        session=session,
        user=user,
        prompt=prompt,
        pending_input="profile:avatar",
    )


def _prepare_avatar(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        width, height = img.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        cropped = img.crop((left, top, left + side, top + side))
        resized = cropped.resize((256, 256))
        output = io.BytesIO()
        resized.save(output, format="JPEG", quality=90)
        return output.getvalue()


async def _handle_registration_login(
    message: Message,
    session: ChatSession,
    value: str,
) -> None:
    if not LOGIN_PATTERN.match(value):
        await message.answer(
            "Логин может содержать латиницу, цифры, точку, дефис, подчёркивание (3–32 символа)."
        )
        return
    storage = _get_storage()
    if await storage.is_login_taken(value):
        await message.answer("Такой логин уже занят. Попробуйте другой.")
        return
    session.temp["register_login"] = value
    session.pending_input = "register:password"
    await message.answer("Логин принят ✅ Теперь придумайте пароль (минимум 6 символов).")


async def _handle_registration_password(
    message: Message,
    session: ChatSession,
    value: str,
    *,
    bot: Bot,
) -> None:
    if len(value) < PASSWORD_MIN_LENGTH:
        await message.answer("Пароль слишком короткий. Минимум 6 символов.")
        return
    login = session.temp.get("register_login")
    if not login:
        session.pending_input = None
        await message.answer("Не удалось определить логин. Начните регистрацию заново.")
        return
    storage = _get_storage()
    tg_user = message.from_user
    tg_name = _format_telegram_name(message)
    try:
        user = await storage.register_user(
            login=login,
            password=value,
            tg_user_id=tg_user.id if tg_user else 0,
            tg_name=tg_name,
            chat_id=message.chat.id,
        )
    except LoginAlreadyExistsError:
        await message.answer("Такой логин уже занят. Попробуйте другой.")
        session.pending_input = "register:login"
        return
    session.authorized_login = login
    session.pending_input = None
    session.temp.clear()
    await message.answer("Регистрация завершена ✅ Профиль создан.")
    await _render_profile(bot, message.chat.id, user, nav_action="replace")


async def _handle_login_login(
    message: Message,
    session: ChatSession,
    value: str,
) -> None:
    storage = _get_storage()
    try:
        user = await storage.load_user(value)
    except LoginNotFoundError:
        await message.answer(
            "Такого аккаунта не существует. Нажмите «Регистрация», чтобы создать новый."
        )
        return
    tg_user = message.from_user
    if tg_user and user.profile.tg_user_id not in (0, tg_user.id):
        await message.answer("Этот логин уже закреплён за другим пользователем.")
        return
    session.temp["login_login"] = value
    session.pending_input = "login:password"
    await message.answer("Введите пароль для входа в аккаунт.")


async def _handle_login_password(
    message: Message,
    session: ChatSession,
    value: str,
    *,
    bot: Bot,
) -> None:
    login = session.temp.get("login_login")
    if not login:
        session.pending_input = None
        await message.answer("Не удалось определить логин. Попробуйте авторизоваться заново.")
        return
    if not _allow_attempt(session):
        await message.answer("Слишком много попыток. Попробуйте снова через несколько минут.")
        return
    storage = _get_storage()
    tg_user = message.from_user
    tg_name = _format_telegram_name(message)
    try:
        user = await storage.authenticate_user(
            login=login,
            password=value,
            tg_user_id=tg_user.id if tg_user else 0,
            tg_name=tg_name,
            chat_id=message.chat.id,
        )
    except LoginNotFoundError:
        await message.answer(
            "Такого аккаунта не существует. Нажмите «Регистрация», чтобы создать новый."
        )
        session.pending_input = "login:login"
        session.temp.clear()
        return
    except LoginOwnershipError:
        await message.answer("Этот логин уже закреплён за другим пользователем.")
        session.pending_input = None
        session.temp.clear()
        return
    except InvalidCredentialsError:
        await message.answer("Неверный пароль. Попробуйте ещё раз.")
        return
    session.authorized_login = login
    session.pending_input = None
    session.temp.clear()
    session.login_attempts.clear()
    await message.answer("Готово! Вы вошли в профиль ✅")
    await _render_profile(bot, message.chat.id, user, nav_action="replace")


def _validate_company(value: str) -> bool:
    return bool(value and len(value) <= 64)


def _validate_email(value: str) -> bool:
    return EMAIL_PATTERN.match(value) is not None


def _validate_wb(value: str) -> bool:
    return WB_PATTERN.match(value) is not None


def _validate_ms(value: str) -> bool:
    return bool(MS_PATTERN_BASIC.match(value) or MS_PATTERN_TOKEN.match(value))


@MENU_ROUTER.message(F.text)
async def handle_text_input(message: Message, bot: Bot, request_id: str, started_at: float) -> None:
    if message.from_user is None:
        return
    session = await session_storage.get_session(message.chat.id)
    pending = session.pending_input
    if not pending:
        return
    value = (message.text or "").strip()
    logger = get_logger(__name__).bind(action="input", request_id=request_id, context=pending)
    if pending == "register:login":
        await _handle_registration_login(message, session, value)
        logger.info(
            "Получен логин для регистрации", outcome="ok", latency_ms=_calc_latency(started_at)
        )
        return
    if pending == "register:password":
        await _handle_registration_password(message, session, value, bot=bot)
        logger.info("Регистрация завершена", outcome="ok", latency_ms=_calc_latency(started_at))
        return
    if pending == "login:login":
        await _handle_login_login(message, session, value)
        logger.info(
            "Получен логин для авторизации", outcome="ok", latency_ms=_calc_latency(started_at)
        )
        return
    if pending == "login:password":
        await _handle_login_password(message, session, value, bot=bot)
        logger.info("Попытка авторизации", outcome="ok", latency_ms=_calc_latency(started_at))
        return
    if pending == "profile:company":
        if not _validate_company(value):
            await message.answer("Название компании должно содержать 1–64 символ.")
            logger.info(
                "Неверное название компании", outcome="fail", latency_ms=_calc_latency(started_at)
            )
            return
        storage = _get_storage()
        if session.authorized_login:
            user = await storage.update_company(session.authorized_login, value)
            session.pending_input = None
            await message.answer("Компания обновлена ✅")
            await _render_profile(bot, message.chat.id, user, nav_action="replace")
            logger.info("Компания обновлена", outcome="ok", latency_ms=_calc_latency(started_at))
        return
    if pending == "profile:email":
        if not _validate_email(value):
            await message.answer("Пожалуйста, укажите корректный email.")
            logger.info("Неверный email", outcome="fail", latency_ms=_calc_latency(started_at))
            return
        storage = _get_storage()
        if session.authorized_login:
            user = await storage.update_email(session.authorized_login, value)
            session.pending_input = None
            await message.answer("Почта сохранена ✅")
            await _render_profile(bot, message.chat.id, user, nav_action="replace")
            logger.info("Email обновлён", outcome="ok", latency_ms=_calc_latency(started_at))
        return
    if pending == "profile:wb":
        if not _validate_wb(value):
            await message.answer("Ключ WB должен содержать 32–128 символов латиницы и цифр.")
            logger.info("Неверный ключ WB", outcome="fail", latency_ms=_calc_latency(started_at))
            return
        storage = _get_storage()
        if session.authorized_login:
            user = await storage.update_wb_key(session.authorized_login, value)
            session.pending_input = None
            masked = _mask_for_log(value)
            await message.answer("Ключ WB сохранён ✅")
            await _render_profile(bot, message.chat.id, user, nav_action="replace")
            logger.info(
                "Ключ WB обновлён", outcome="ok", mask=masked, latency_ms=_calc_latency(started_at)
            )
        return
    if pending == "profile:ms":
        if not _validate_ms(value):
            await message.answer(
                "Ключ «МойСклад» должен быть формата Basic ... или 8–128 символов."
            )
            logger.info(
                "Неверный ключ МойСклад", outcome="fail", latency_ms=_calc_latency(started_at)
            )
            return
        storage = _get_storage()
        if session.authorized_login:
            user = await storage.update_ms_key(session.authorized_login, value)
            session.pending_input = None
            masked = _mask_for_log(value)
            await message.answer("Ключ «МойСклад» сохранён ✅")
            await _render_profile(bot, message.chat.id, user, nav_action="replace")
            logger.info(
                "Ключ МойСклад обновлён",
                outcome="ok",
                mask=masked,
                latency_ms=_calc_latency(started_at),
            )
        return
    logger.info("Неизвестный контекст ввода", outcome="fail", latency_ms=_calc_latency(started_at))


@MENU_ROUTER.message(F.photo | F.document)
async def handle_media_input(
    message: Message, bot: Bot, request_id: str, started_at: float
) -> None:
    session = await session_storage.get_session(message.chat.id)
    if session.pending_input != "profile:avatar":
        return
    if not session.authorized_login:
        session.pending_input = None
        return
    logger = get_logger(__name__).bind(action="profile.avatar.save", request_id=request_id)
    data_stream = io.BytesIO()
    file_obj: PhotoSize | Document | None = None
    if message.photo:
        file_obj = message.photo[-1]
    elif (
        message.document
        and message.document.mime_type
        and message.document.mime_type.startswith("image/")
    ):
        file_obj = message.document
    if file_obj is None:
        await message.answer("Пожалуйста, отправьте фотографию или изображение файлом.")
        logger.info("Неверный тип вложения", outcome="fail")
        return
    await bot.download(file_obj, destination=data_stream)
    try:
        avatar_bytes = _prepare_avatar(data_stream.getvalue())
    except Exception as exc:  # pragma: no cover - Pillow errors
        await message.answer("Не удалось обработать изображение. Попробуйте другой файл.")
        logger.warning("Ошибка обработки аватара", outcome="fail", error=str(exc))
        return
    storage = _get_storage()
    user = await storage.save_avatar(session.authorized_login, avatar_bytes)
    session.pending_input = None
    await message.answer("Аватар обновлён ✅")
    await _render_profile(bot, message.chat.id, user, nav_action="replace")
    latency = _calc_latency(started_at)
    logger.info("Аватар сохранён", outcome="ok", latency_ms=latency)


__all__ = ["MENU_ROUTER"]

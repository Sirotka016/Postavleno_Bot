import asyncio
from dataclasses import dataclass

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from postavleno_bot.handlers.cmd_help import HELP_OK_CALLBACK, handle_help
from postavleno_bot.handlers.cb_help_ok import handle_help_ok
from postavleno_bot.handlers.utils import AUTH_USER_KEY
from postavleno_bot.services.accounts import get_accounts_repo


@dataclass
class DummyUser:
    username: str | None = None
    first_name: str | None = None


class DummyMessage:
    def __init__(self, user: DummyUser | None) -> None:
        self.from_user = user
        self.answers: list[dict[str, object]] = []

    async def answer(
        self,
        text: str,
        *,
        disable_web_page_preview: bool = False,
        reply_markup: object | None = None,
    ) -> None:
        self.answers.append(
            {
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
                "reply_markup": reply_markup,
            }
        )


class DummyCallback:
    def __init__(self) -> None:
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class DummyBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class DummyChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class DummyMessageObj:
    def __init__(self, chat_id: int, message_id: int) -> None:
        self.chat = DummyChat(chat_id)
        self.message_id = message_id


class HelpCallback(DummyCallback):
    def __init__(self, chat_id: int, message_id: int, bot: DummyBot | None) -> None:
        super().__init__()
        self.message = DummyMessageObj(chat_id, message_id)
        self.bot = bot
        self.data = HELP_OK_CALLBACK


class HelpCallbackNoMessage(DummyCallback):
    def __init__(self) -> None:
        super().__init__()
        self.message = None
        self.bot = DummyBot()
        self.data = HELP_OK_CALLBACK


async def _create_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=42, chat_id=1001, user_id=1001)
    return FSMContext(storage=storage, key=key)


def _build_expected_help(name: str, authorized: bool) -> str:
    header = [
        f"Привет, {name}! ✨",
        "Меня зовут Postavleno_Bot.",
        "",
        "Как начать:",
    ]
    if authorized:
        body = [
            "1) Откройте «Профиль» и при необходимости дополните данные:",
            "   — «Компания» — укажите/измените название.",
            "   — «Почта» — привяжите и подтвердите email (на него придёт код).",
            "   — «WB API» — добавьте или обновите ключ из кабинета WB (Доступ к API).",
            "2) Вернитесь на главное окно и выберите нужную выгрузку.",
            "3) «Обновить» — перезапрос данных и актуализация статусов.",
            "4) «Выйти» — завершить сессию.",
        ]
    else:
        body = [
            "1) Пройдите авторизацию/регистрацию, чтобы продолжить.",
            "2) Нажмите «Профиль» и заполните:",
            "   — «Компания» — укажите название (можно изменить позже).",
            "   — «Почта» — привяжите и подтвердите email (на него придёт код).",
            "   — «WB API» — добавьте ключ из кабинета WB (Доступ к API).",
            "3) Вернитесь на главное окно и выберите нужную выгрузку.",
            "4) «Обновить» — перезапрос данных и актуализация статусов.",
            "5) «Выйти» — завершить сессию.",
        ]
    return "\n".join([*header, *body])


@pytest.mark.parametrize(
    "user, expected_name",
    [
        (DummyUser(username="guest"), "@guest"),
        (DummyUser(username=None, first_name="Алиса"), "Алиса"),
    ],
)
def test_help_unauthorized_text(user: DummyUser, expected_name: str) -> None:
    async def runner() -> None:
        state = await _create_state()
        message = DummyMessage(user)

        await handle_help(message, state)

        assert message.answers, "handler must send a response"
        payload = message.answers[0]
        assert payload["disable_web_page_preview"] is True
        assert payload["reply_markup"] is not None
        text = str(payload["text"])
        assert text == _build_expected_help(expected_name, authorized=False)

    asyncio.run(runner())


def test_help_authorized_text() -> None:
    async def runner() -> None:
        state = await _create_state()
        repo = get_accounts_repo()
        profile = repo.create(display_login="HelpUser", password="secret123")
        await state.update_data({AUTH_USER_KEY: profile.username})

        message = DummyMessage(DummyUser(username=None, first_name=None))
        await handle_help(message, state)

        assert message.answers, "handler must send a response"
        payload = message.answers[0]
        assert payload["disable_web_page_preview"] is True
        assert payload["reply_markup"] is not None
        text = str(payload["text"])
        assert text == _build_expected_help("HelpUser", authorized=True)

    asyncio.run(runner())


def test_help_has_single_ok_button() -> None:
    async def runner() -> None:
        state = await _create_state()
        message = DummyMessage(DummyUser(username="guest"))

        await handle_help(message, state)

        payload = message.answers[0]
        markup = payload["reply_markup"]
        assert getattr(markup, "inline_keyboard", None) is not None
        buttons = markup.inline_keyboard  # type: ignore[assignment]
        assert len(buttons) == 1 and len(buttons[0]) == 1
        button = buttons[0][0]
        assert button.text == "Понятно"
        assert button.callback_data == HELP_OK_CALLBACK

    asyncio.run(runner())


def test_help_ok_deletes_message() -> None:
    async def runner() -> None:
        bot = DummyBot()
        callback = HelpCallback(chat_id=555, message_id=999, bot=bot)

        await handle_help_ok(callback)

        assert bot.deleted == [(555, 999)]
        assert callback.answered is True

    asyncio.run(runner())


def test_help_ok_handles_missing_message() -> None:
    async def runner() -> None:
        callback = HelpCallbackNoMessage()

        await handle_help_ok(callback)

        assert callback.answered is True

    asyncio.run(runner())

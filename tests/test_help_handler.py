import asyncio
from dataclasses import dataclass

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from postavleno_bot.handlers.help import handle_help
from postavleno_bot.handlers.utils import AUTH_USER_KEY
from postavleno_bot.services.accounts import get_accounts_repo


@dataclass
class DummyUser:
    username: str | None = None
    first_name: str | None = None
    full_name: str | None = None


class DummyMessage:
    def __init__(self, user: DummyUser | None) -> None:
        self.from_user = user
        self.answers: list[dict[str, object]] = []

    async def answer(self, text: str, disable_web_page_preview: bool = False) -> None:
        self.answers.append({"text": text, "disable_web_page_preview": disable_web_page_preview})


async def _create_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=42, chat_id=1001, user_id=1001)
    return FSMContext(storage=storage, key=key)


@pytest.mark.parametrize(
    "user, expected_name",
    [
        (DummyUser(username="guest"), "@guest"),
        (DummyUser(first_name="Alice"), "Alice"),
    ],
)
def test_help_command_for_guests(user: DummyUser, expected_name: str) -> None:
    async def runner() -> None:
        state = await _create_state()
        message = DummyMessage(user)

        await handle_help(message, state)

        assert message.answers, "handler must send a response"
        payload = message.answers[0]
        assert payload["disable_web_page_preview"] is True
        text = str(payload["text"])
        assert f"Привет, {expected_name}! ✨" in text
        assert "Пройдите авторизацию/регистрацию" in text

    asyncio.run(runner())


def test_help_command_for_authorized_user() -> None:
    async def runner() -> None:
        state = await _create_state()
        repo = get_accounts_repo()
        profile = repo.create(display_login="HelpUser", password="secret123")
        await state.update_data({AUTH_USER_KEY: profile.username})

        message = DummyMessage(None)
        await handle_help(message, state)

        assert message.answers, "handler must send a response"
        payload = message.answers[0]
        assert payload["disable_web_page_preview"] is True
        text = str(payload["text"])
        assert "Откройте «Профиль»" in text
        assert "Пройдите авторизацию/регистрацию" not in text
        assert "Привет, HelpUser! ✨" in text

    asyncio.run(runner())

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from postavleno_bot.handlers.pages import render_home
from postavleno_bot.start.ability_registry import ability_lines


@dataclass
class DummyUser:
    username: str | None = None
    first_name: str | None = None


class CaptureCard:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def render(self, bot: object, chat_id: int, text: str, **kwargs: Any) -> int:
        self.payloads.append({"bot": bot, "chat_id": chat_id, "text": text, **kwargs})
        return 101


async def _create_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=42, chat_id=1001, user_id=1001)
    return FSMContext(storage=storage, key=key)


def test_start_injects_abilities_block(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        capture = CaptureCard()
        monkeypatch.setattr("postavleno_bot.handlers.pages.card_manager", capture)

        state = await _create_state()
        user = DummyUser(username="tester")

        await render_home(bot=object(), state=state, chat_id=777, tg_user=user)

        assert capture.payloads, "render_home must call card manager"
        text = capture.payloads[0]["text"]
        header_lines = [
            "Привет, @tester! ✨",
            "Меня зовут Postavleno_Bot.",
            "",
            "Что я умею:",
            *ability_lines(),
        ]
        expected_top = "\n".join(header_lines)
        assert text.startswith(f"{expected_top}\n\n"), text

    asyncio.run(runner())


def test_start_mention_username_or_first_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def runner() -> None:
        capture = CaptureCard()
        monkeypatch.setattr("postavleno_bot.handlers.pages.card_manager", capture)

        state = await _create_state()
        user = DummyUser(username=None, first_name="Иван")

        await render_home(bot=object(), state=state, chat_id=888, tg_user=user)

        text = capture.payloads[0]["text"]
        assert text.startswith("Привет, Иван! ✨"), text

    asyncio.run(runner())

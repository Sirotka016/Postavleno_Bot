from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from postavleno_bot.handlers import menu
from postavleno_bot.handlers.menu import (
    LOCAL_UPLOAD_PROGRESS_TEXT,
    SCREEN_LOCAL_UPLOAD,
    handle_local_back,
    handle_local_document,
    maybe_delete_user_message,
)
from postavleno_bot.state.session import ChatSession, ScreenState, session_storage


@pytest.mark.asyncio()
async def test_user_messages_not_deleted_during_upload_screen() -> None:
    chat_id = 123
    session = ChatSession(expecting_upload=True)
    message = SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=42)
    bot = SimpleNamespace(delete_message=AsyncMock())

    deleted = await maybe_delete_user_message(
        bot=bot,
        message=message,
        session=session,
        logger=None,
    )

    assert not deleted
    bot.delete_message.assert_not_awaited()


@pytest.mark.asyncio()
async def test_document_kept_and_processed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chat_id = 555
    await session_storage.clear(chat_id)
    session = await session_storage.get_session(chat_id)
    session.history = [ScreenState(name=SCREEN_LOCAL_UPLOAD, params={})]
    session.expecting_upload = True
    await session_storage.set_last_message_id(chat_id, 999)

    edit_calls: list[str] = []

    async def fake_safe_edit(bot, chat_id: int, message_id: int, text: str, inline_markup=None):
        edit_calls.append(text)
        return SimpleNamespace(message_id=message_id)

    safe_delete_calls: list[tuple[int, int]] = []

    async def fake_safe_delete(bot, chat_id: int, message_id: int) -> bool:
        safe_delete_calls.append((chat_id, message_id))
        return True

    download_mock = AsyncMock()

    class DummyFile:
        def read(self) -> bytes:
            return b"dummy"

    download_mock.return_value = DummyFile()

    dataframe = pd.DataFrame(
        {
            "supplierArticle": ["ART-1"],
            "warehouseName": ["WH"],
            "quantity": [10],
        }
    )

    def fake_dataframe_from_bytes(data: bytes, filename: str | None):
        return dataframe

    classify_called: list[pd.DataFrame] = []

    def fake_classify(df: pd.DataFrame) -> str:
        classify_called.append(df)
        return "WB"

    def fake_save_wb_upload(chat: int, df: pd.DataFrame) -> Path:
        return tmp_path / "wb.xlsx"

    bot = SimpleNamespace(delete_message=AsyncMock(), download=download_mock)

    monkeypatch.setattr(menu, "safe_edit", fake_safe_edit)
    monkeypatch.setattr(menu, "safe_delete", fake_safe_delete)
    monkeypatch.setattr(menu, "dataframe_from_bytes", fake_dataframe_from_bytes)
    monkeypatch.setattr(menu, "classify_dataframe", fake_classify)
    monkeypatch.setattr(menu, "save_wb_upload", fake_save_wb_upload)

    message = SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        message_id=321,
        document=SimpleNamespace(file_id="1", file_name="file.xlsx"),
    )

    await handle_local_document(message, bot, request_id="req", started_at=0.0)

    bot.delete_message.assert_not_awaited()
    assert download_mock.await_count == 1
    assert len(classify_called) == 1
    assert any(LOCAL_UPLOAD_PROGRESS_TEXT in text for text in edit_calls)
    assert all(message_id != message.message_id for _, message_id in safe_delete_calls)
    assert session.expecting_upload is True

    await session_storage.clear(chat_id)


@pytest.mark.asyncio()
async def test_back_turns_off_wait_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_id = 777
    await session_storage.clear(chat_id)
    session = await session_storage.get_session(chat_id)
    session.history = [
        ScreenState(name="LOCAL_OPEN", params={}),
        ScreenState(name=SCREEN_LOCAL_UPLOAD, params={}),
    ]
    session.expecting_upload = True
    await session_storage.set_last_message_id(chat_id, 123)

    async def fake_safe_edit(bot, chat_id: int, message_id: int, text: str, inline_markup=None):
        return SimpleNamespace(message_id=message_id)

    async def fake_safe_delete(bot, chat_id: int, message_id: int) -> bool:
        return True

    bot = SimpleNamespace(delete_message=AsyncMock())
    monkeypatch.setattr(menu, "safe_edit", fake_safe_edit)
    monkeypatch.setattr(menu, "safe_delete", fake_safe_delete)

    class DummyCallback:
        def __init__(self) -> None:
            self.message = SimpleNamespace(chat=SimpleNamespace(id=chat_id))

        async def answer(self, *args, **kwargs) -> None:  # pragma: no cover - stub
            return None

    callback = DummyCallback()

    await handle_local_back(callback, bot, request_id="req", started_at=0.0)

    assert session.expecting_upload is False

    await session_storage.clear(chat_id)

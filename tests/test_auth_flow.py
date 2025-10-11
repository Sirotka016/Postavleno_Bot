from __future__ import annotations

from types import SimpleNamespace

import pytest

from postavleno_bot.handlers import menu
from postavleno_bot.state.session import session_storage
from postavleno_bot.utils.strings import mask_secret


@pytest.mark.asyncio
async def test_full_authorization_and_profile_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_id = 1001
    user_id = 9001
    username = "tester"

    sent_messages: list[str] = []

    class DummyMessage(SimpleNamespace):
        message_id: int

    async def fake_safe_send(bot, chat_id: int, text: str, reply_markup):  # type: ignore[override]
        sent_messages.append(text)
        return DummyMessage(message_id=len(sent_messages))

    async def fake_safe_edit(bot, chat_id: int, message_id: int, text: str, inline_markup):  # type: ignore[override]
        sent_messages.append(text)
        return DummyMessage(message_id=message_id)

    monkeypatch.setattr(menu, "safe_send", fake_safe_send)
    monkeypatch.setattr(menu, "safe_edit", fake_safe_edit)

    await session_storage.clear(chat_id)

    user = await menu._ensure_user(tg_user_id=user_id, chat_id=chat_id, username=username)
    assert user.is_registered is False
    assert user.tg_bot_token_enc is None

    await menu._render_auth(bot=None, chat_id=chat_id, user=user, nav_action="push")
    session = await session_storage.get_session(chat_id)
    assert session.pending_input == "auth:tg_bot"

    user = await menu._save_token(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        kind="tg_bot",
        token="1234567890:TESTTOKENforAUTHFLOW123456789012345",
    )
    assert user.tg_bot_token_enc is not None
    assert user.is_registered is False
    await menu._render_auth(bot=None, chat_id=chat_id, user=user, nav_action="replace")
    session = await session_storage.get_session(chat_id)
    assert session.pending_input == "auth:wb_api"

    user = await menu._save_token(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        kind="wb_api",
        token="A" * 64,
    )
    assert user.wb_api_token_enc is not None
    assert user.is_registered is False

    user = await menu._save_token(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        kind="moysklad",
        token="Basic dXNlcjpwYXNz",
    )
    assert user.moysklad_api_token_enc is not None
    assert user.is_registered is True
    assert user.registered_at is not None

    await menu._render_profile(bot=None, chat_id=chat_id, user=user, nav_action="replace")
    session = await session_storage.get_session(chat_id)
    assert session.pending_input is None
    assert any("TG BOT" in text for text in sent_messages)

    user = await menu._update_display_name(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        display_name="Алексей",
    )
    assert user.display_name == "Алексей"

    user = await menu._update_company_name(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        company_name="ООО Ромашка",
    )
    assert user.company_name == "ООО Ромашка"

    new_token = "9876543210:UPDATEDTOKENVALUEAAABBBCCC1234567890"
    assert menu._validate_token("tg_bot", new_token)
    user = await menu._save_token(
        tg_user_id=user_id,
        chat_id=chat_id,
        username=username,
        kind="tg_bot",
        token=new_token,
    )
    plain_token = menu._get_token_plain(user, "tg_bot")
    assert plain_token == new_token
    assert mask_secret(plain_token) == mask_secret(new_token)

    invalid_token = "short"
    assert menu._validate_token("wb_api", invalid_token) is False

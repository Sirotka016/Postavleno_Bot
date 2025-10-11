from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from postavleno_bot.core.config import get_settings
from postavleno_bot.core.crypto import decrypt_json
from postavleno_bot.handlers.menu import _prepare_avatar
from postavleno_bot.services.users import (
    InvalidCredentialsError,
    LoginAlreadyExistsError,
    LoginOwnershipError,
    get_user_storage,
)


@pytest.mark.asyncio
async def test_registration_creates_profile() -> None:
    settings = get_settings()
    storage = get_user_storage()
    user = await storage.register_user(
        login="demo",
        password="secret123",
        tg_user_id=123,
        tg_name="Tester",
        chat_id=555,
    )
    profile_dir = settings.users_dir / "demo"
    profile_path = profile_dir / "profile.json"
    secrets_path = profile_dir / "secrets.json.enc"
    assert profile_path.exists()
    assert secrets_path.exists()
    profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile_data["company"] == "demo"
    assert profile_data["tg_user_id"] == 123
    assert profile_data["tg_name"] == "Tester"
    secrets = decrypt_json(secrets_path.read_bytes())
    assert secrets["password_hash"] != "secret123"
    assert secrets["wb_api"] is None
    assert user.profile.company == "demo"


@pytest.mark.asyncio
async def test_duplicate_login_is_rejected() -> None:
    storage = get_user_storage()
    await storage.register_user(
        login="unique",
        password="secret123",
        tg_user_id=1,
        tg_name="First",
        chat_id=42,
    )
    with pytest.raises(LoginAlreadyExistsError):
        await storage.register_user(
            login="unique",
            password="anotherpass",
            tg_user_id=2,
            tg_name="Second",
            chat_id=24,
        )


@pytest.mark.asyncio
async def test_authentication_and_ownership() -> None:
    storage = get_user_storage()
    await storage.register_user(
        login="owner",
        password="password1",
        tg_user_id=10,
        tg_name="Owner",
        chat_id=1,
    )
    user = await storage.authenticate_user(
        login="owner",
        password="password1",
        tg_user_id=10,
        tg_name="Owner",
        chat_id=2,
    )
    assert user.profile.last_chat_id == 2
    with pytest.raises(InvalidCredentialsError):
        await storage.authenticate_user(
            login="owner",
            password="wrong",
            tg_user_id=10,
            tg_name="Owner",
            chat_id=2,
        )
    with pytest.raises(LoginOwnershipError):
        await storage.authenticate_user(
            login="owner",
            password="password1",
            tg_user_id=11,
            tg_name="Intruder",
            chat_id=3,
        )


@pytest.mark.asyncio
async def test_save_avatar(tmp_path: Path) -> None:
    storage = get_user_storage()
    await storage.register_user(
        login="avatar",
        password="secret123",
        tg_user_id=5,
        tg_name="Avatar User",
        chat_id=9,
    )
    image_path = tmp_path / "source.png"
    Image.new("RGB", (400, 200), color="blue").save(image_path)
    data = image_path.read_bytes()
    prepared = _prepare_avatar(data)
    user = await storage.save_avatar("avatar", prepared)
    saved_path = get_settings().users_dir / "avatar" / "avatar.jpg"
    assert saved_path.exists()
    with Image.open(saved_path) as img:
        assert img.size == (256, 256)
    assert user.profile.avatar_filename == "avatar.jpg"


@pytest.mark.asyncio
async def test_update_api_keys() -> None:
    storage = get_user_storage()
    await storage.register_user(
        login="keys",
        password="secret123",
        tg_user_id=7,
        tg_name="Key Owner",
        chat_id=77,
    )
    await storage.update_wb_key("keys", "A" * 64)
    await storage.update_ms_key("keys", "Basic ZGVtbzp0ZXN0")
    secrets_path = get_settings().users_dir / "keys" / "secrets.json.enc"
    secrets = decrypt_json(secrets_path.read_bytes())
    assert secrets["wb_api"].startswith("A")
    assert secrets["ms_api"].startswith("Basic")

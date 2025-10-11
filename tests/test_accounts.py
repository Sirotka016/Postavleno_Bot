from datetime import UTC, datetime

import pytest

from postavleno_bot.repositories.accounts_fs import AccountAlreadyExistsError
from postavleno_bot.services.accounts import get_accounts_repo


def test_create_and_retrieve_account() -> None:
    repo = get_accounts_repo()
    profile = repo.create(display_login="My.Shop", password="secret123")
    assert profile.username == "my.shop"
    loaded = repo.get("my.shop")
    assert loaded.display_login == "My.Shop"
    assert repo.verify_password(loaded, "secret123")
    assert not repo.verify_password(loaded, "other")
    assert isinstance(loaded.created_at, datetime)
    assert loaded.created_at.tzinfo is UTC


def test_duplicate_login_is_rejected() -> None:
    repo = get_accounts_repo()
    repo.create(display_login="DemoUser", password="password")
    with pytest.raises(AccountAlreadyExistsError):
        repo.create(display_login="demouser", password="password")


def test_update_tokens() -> None:
    repo = get_accounts_repo()
    profile = repo.create(display_login="TokenUser", password="password")
    updated = repo.set_wb_api(profile.username, "A" * 64)
    assert updated.wb_api == "A" * 64
    updated = repo.set_ms_api(profile.username, "B" * 32)
    assert updated.ms_api == "B" * 32

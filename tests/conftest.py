from __future__ import annotations

from pathlib import Path

import pytest

from postavleno_bot.core.config import get_settings
from postavleno_bot.services.accounts import get_accounts_repo


@pytest.fixture(autouse=True)
def configure_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890:TESTTOKENforAUTHFLOW123456789012345")
    monkeypatch.setenv("ACCOUNTS_DIR", str(tmp_path / "accounts"))
    get_settings.cache_clear()
    get_accounts_repo.cache_clear()
    yield
    get_accounts_repo.cache_clear()
    get_settings.cache_clear()

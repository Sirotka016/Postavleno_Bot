from __future__ import annotations

from pathlib import Path

import pytest

from postavleno_bot.core.config import get_settings
from postavleno_bot.db.engine import create_all

TEST_SECRET_KEY = "x1KjWbD5_yN1Hx0zP8z2dGkRWc5lN6P7i0p9w4s6c7o="


@pytest.fixture(autouse=True)
def configure_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890:TESTTOKENforAUTHFLOW123456789012345")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def initialize_database() -> None:
    await create_all()
    yield

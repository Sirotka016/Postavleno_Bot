import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import sys
import types

if "aiosmtplib" not in sys.modules:
    class _TempSMTP:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - stub
            pass

    sys.modules["aiosmtplib"] = types.SimpleNamespace(SMTP=_TempSMTP, SMTPException=Exception)

import pytest

from postavleno_bot.services import email_verification
from postavleno_bot.services.accounts import get_accounts_repo


class EmailRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def test_email_verification_success_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = get_accounts_repo()
    profile = repo.create(display_login="EmailUser", password="password")

    recorder = EmailRecorder()
    monkeypatch.setattr(email_verification, "send_email", recorder)
    monkeypatch.setattr(email_verification, "generate_code", lambda length=6: "123456")

    fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(email_verification, "_now", lambda: fixed_now)

    updated = asyncio.run(
        email_verification.start_email_verification(profile, "user@example.com")
    )

    assert updated.email == "user@example.com"
    assert updated.email_verified is False
    assert updated.email_pending_hash is not None
    assert updated.email_pending_expires_at == fixed_now + timedelta(minutes=email_verification.CODE_TTL_MINUTES)

    assert recorder.calls
    call = recorder.calls[0]
    assert call["to_email"] == "user@example.com"
    assert "123456" in call["body"]

    monkeypatch.setattr(email_verification, "_now", lambda: fixed_now + timedelta(minutes=5))
    success, verified = email_verification.verify_email_code(updated, "123456")
    assert success is True
    assert verified.email_verified is True
    assert verified.email_pending_hash is None
    assert verified.email_pending_expires_at is None


def test_email_verification_rejects_invalid_or_expired_code(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = get_accounts_repo()
    profile = repo.create(display_login="EmailFail", password="password")

    recorder = EmailRecorder()
    monkeypatch.setattr(email_verification, "send_email", recorder)
    monkeypatch.setattr(email_verification, "generate_code", lambda length=6: "654321")

    fixed_now = datetime(2024, 2, 1, 8, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(email_verification, "_now", lambda: fixed_now)

    pending = asyncio.run(
        email_verification.start_email_verification(profile, "fail@example.com")
    )

    # wrong code
    monkeypatch.setattr(email_verification, "_now", lambda: fixed_now + timedelta(minutes=1))
    success, same_profile = email_verification.verify_email_code(pending, "000000")
    assert success is False
    assert same_profile.email_verified is False

    # expired code
    monkeypatch.setattr(email_verification, "_now", lambda: fixed_now + timedelta(minutes=11))
    success, expired_profile = email_verification.verify_email_code(pending, "654321")
    assert success is False
    assert expired_profile.email_verified is False
    assert expired_profile.email_pending_hash == pending.email_pending_hash

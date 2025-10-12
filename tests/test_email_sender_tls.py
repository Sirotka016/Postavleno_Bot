import asyncio
from email.message import EmailMessage
import sys
import types

if "aiosmtplib" not in sys.modules:
    class _TempSMTP:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - stub
            pass

    sys.modules["aiosmtplib"] = types.SimpleNamespace(SMTP=_TempSMTP, SMTPException=Exception)

import pytest

from postavleno_bot.utils import email_sender


class SMTPStub:
    instances: list["SMTPStub"] = []

    def __init__(self, *, hostname: str, port: int, use_tls: bool = False, timeout: int | None = None) -> None:
        self.hostname = hostname
        self.port = port
        self.use_tls = use_tls
        self.timeout = timeout
        self.connected = False
        self.starttls_calls = 0
        self.login_calls: list[tuple[str, str]] = []
        self.sent_messages: list[EmailMessage] = []
        self.quit_called = False
        SMTPStub.instances.append(self)

    async def connect(self) -> None:
        self.connected = True

    async def starttls(self) -> None:
        self.starttls_calls += 1

    async def login(self, username: str, password: str) -> None:
        self.login_calls.append((username, password))

    async def send_message(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)

    async def quit(self) -> None:
        self.quit_called = True


def test_send_email_uses_starttls_for_587(monkeypatch: pytest.MonkeyPatch) -> None:
    SMTPStub.instances.clear()
    monkeypatch.setattr(email_sender, "SMTP", SMTPStub)

    asyncio.run(
        email_sender.send_email(
            host="smtp.gmail.com",
            port=587,
            username="user@example.com",
            password="secret",
            sender_name="Postavleno",
            to_email="dest@example.com",
            subject="Test",
            body="Hello",
        )
    )

    assert len(SMTPStub.instances) == 1
    instance = SMTPStub.instances[0]
    assert instance.port == 587
    assert instance.use_tls is False
    assert instance.connected
    assert instance.starttls_calls == 1
    assert instance.login_calls == [("user@example.com", "secret")]
    assert instance.sent_messages and instance.sent_messages[0]["To"] == "dest@example.com"
    assert instance.quit_called


def test_send_email_skips_starttls_for_465(monkeypatch: pytest.MonkeyPatch) -> None:
    SMTPStub.instances.clear()
    monkeypatch.setattr(email_sender, "SMTP", SMTPStub)

    asyncio.run(
        email_sender.send_email(
            host="smtp.gmail.com",
            port=465,
            username="user@example.com",
            password="secret",
            sender_name="Postavleno",
            to_email="dest@example.com",
            subject="Test",
            body="Hello",
        )
    )

    assert len(SMTPStub.instances) == 1
    instance = SMTPStub.instances[0]
    assert instance.port == 465
    assert instance.use_tls is True
    assert instance.starttls_calls == 0
    assert instance.quit_called

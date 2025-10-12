"""Email verification workflow."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt

from ..core.config import get_settings
from ..repositories import AccountProfile
from ..utils.email_sender import send_email
from .accounts import get_accounts_repo

CODE_TTL_MINUTES = 10
EMAIL_SUBJECT = "Подтверждение почты — Postavleno_Bot"
EMAIL_BODY_TEMPLATE = """Здравствуйте!

Вы запросили подтверждение почты для аккаунта в Postavleno_Bot.
Ваш одноразовый код: {code}

Скопируйте код и отправьте его боту в ответ на запрос.
Код действует {ttl} минут.

Если это были не вы — просто игнорируйте письмо.
Мы никогда не просим пароль от вашего аккаунта.

— Команда Postavleno_Bot
"""


def _now() -> datetime:
    return datetime.now(UTC)


def generate_code(length: int = 6) -> str:
    """Return a numeric verification code of *length* digits."""

    return "".join(secrets.choice("0123456789") for _ in range(length))


def _hash_code(code: str) -> str:
    hashed = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def _check_code(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # pragma: no cover - defensive
        return False


async def start_email_verification(profile: AccountProfile, email: str) -> AccountProfile:
    """Generate a code, persist metadata, and deliver an email."""

    repo = get_accounts_repo()
    code = generate_code()
    expires_at = _now() + timedelta(minutes=CODE_TTL_MINUTES)
    updated = repo.update_fields(
        profile.username,
        email=email,
        email_verified=False,
        email_pending_hash=_hash_code(code),
        email_pending_expires_at=expires_at,
    )

    settings = get_settings()
    await send_email(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password.get_secret_value(),
        sender_name=settings.smtp_sender,
        to_email=email,
        subject=EMAIL_SUBJECT,
        body=EMAIL_BODY_TEMPLATE.format(code=code, ttl=CODE_TTL_MINUTES),
    )
    return updated


def verify_email_code(profile: AccountProfile, code: str) -> tuple[bool, AccountProfile]:
    """Validate *code* and update the profile when successful."""

    if not profile.email_pending_hash or not profile.email_pending_expires_at:
        return False, profile
    if _now() > profile.email_pending_expires_at:
        return False, profile
    if not _check_code(code, profile.email_pending_hash):
        return False, profile

    repo = get_accounts_repo()
    updated = repo.update_fields(
        profile.username,
        email_verified=True,
        email_pending_hash=None,
        email_pending_expires_at=None,
    )
    return True, updated


__all__ = [
    "CODE_TTL_MINUTES",
    "EMAIL_BODY_TEMPLATE",
    "EMAIL_SUBJECT",
    "generate_code",
    "start_email_verification",
    "verify_email_code",
]

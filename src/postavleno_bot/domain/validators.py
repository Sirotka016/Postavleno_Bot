"""Input validators used across the bot."""

from __future__ import annotations

import re

RE_LOGIN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
RE_WB = re.compile(r"^[ -~]{32,512}$")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_login(value: str) -> bool:
    """Return ``True`` when *value* is a valid login."""

    return bool(RE_LOGIN.fullmatch(value))


def validate_wb(value: str) -> bool:
    """Return ``True`` when *value* looks like a WB API key."""

    return bool(RE_WB.fullmatch(value.strip()))


def validate_company_name(value: str) -> bool:
    """Return ``True`` when *value* looks like a company name (1–70 chars)."""

    stripped = value.strip()
    if "\n" in value or "\r" in value:
        return False
    return 1 <= len(stripped) <= 70


def validate_email(value: str) -> bool:
    """Return ``True`` when *value* looks like an email address."""

    return bool(RE_EMAIL.fullmatch(value.strip()))


__all__ = [
    "validate_company_name",
    "validate_email",
    "validate_login",
    "validate_wb",
    "RE_EMAIL",
    "RE_LOGIN",
    "RE_WB",
]

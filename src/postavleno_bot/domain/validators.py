"""Input validators used across the bot."""

from __future__ import annotations

import re

RE_LOGIN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
RE_WB = re.compile(r"^[ -~]{32,512}$")
RE_MS = re.compile(r"^[A-Za-z0-9._:/+=-]{16,4096}$")


def validate_login(value: str) -> bool:
    """Return ``True`` when *value* is a valid login."""

    return bool(RE_LOGIN.fullmatch(value))


def validate_wb(value: str) -> bool:
    """Return ``True`` when *value* looks like a WB API key."""

    return bool(RE_WB.fullmatch(value.strip()))


def validate_ms(value: str) -> bool:
    """Return ``True`` when *value* looks like a MoySklad token."""

    return bool(RE_MS.fullmatch(value.strip()))


def validate_company_name(value: str) -> bool:
    """Return ``True`` when *value* looks like a company name (2–64 chars)."""

    stripped = value.strip()
    return 2 <= len(stripped) <= 64


__all__ = [
    "validate_company_name",
    "validate_login",
    "validate_ms",
    "validate_wb",
    "RE_LOGIN",
    "RE_MS",
    "RE_WB",
]

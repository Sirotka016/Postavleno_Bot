"""Utility helpers for presenting user-facing values."""

from __future__ import annotations

from datetime import datetime


def format_date_ru(value: datetime) -> str:
    """Format ``value`` using Russian day-first notation ``DD.MM.YYYY``.

    The original calendar date is preserved without converting the timestamp to
    the local timezone to avoid accidental day rollovers for values close to
    midnight in UTC.
    """

    d = value.date()
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def mask_token(token: str | None, left: int = 4, right: int = 4) -> str:
    """Return a partially masked token for safer display in chats.

    ``left`` and ``right`` define how many characters from the beginning and the
    end of the token should remain visible. When the token is shorter than the
    combined visible characters the original value is returned unchanged. Empty
    values are replaced with an em dash.
    """

    if not token:
        return "—"

    if len(token) <= left + right:
        return token

    return f"{token[:left]}…{token[-right:]}"


__all__ = ["format_date_ru", "mask_token"]

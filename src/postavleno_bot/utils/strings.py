from __future__ import annotations

from datetime import datetime


def mask_secret(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) < 10:
        return "***"
    return f"{value[:5]}…{value[-4:]}"


def format_datetime(moment: datetime | None) -> str:
    if moment is None:
        return "—"
    return moment.strftime("%d.%m.%Y %H:%M")

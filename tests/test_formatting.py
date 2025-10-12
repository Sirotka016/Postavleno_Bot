from __future__ import annotations

from datetime import UTC, datetime

import pytest

from postavleno_bot.utils.formatting import format_date_ru, mask_token


@pytest.mark.parametrize(
    "value,expected",
    [
        (datetime(2024, 1, 15, 12, 30, tzinfo=UTC), "15.01.2024"),
        (datetime(2024, 12, 31, 23, 59, tzinfo=UTC), "31.12.2024"),
    ],
)
def test_format_date_ru(value: datetime, expected: str) -> None:
    assert format_date_ru(value) == expected


@pytest.mark.parametrize(
    "token,left,right,expected",
    [
        (None, 4, 4, "—"),
        ("", 4, 4, "—"),
        ("abcd", 2, 2, "abcd"),
        ("abcdef", 2, 2, "ab…ef"),
        ("abcdefgh", 3, 3, "abc…fgh"),
    ],
)
def test_mask_token(token: str | None, left: int, right: int, expected: str) -> None:
    assert mask_token(token, left=left, right=right) == expected

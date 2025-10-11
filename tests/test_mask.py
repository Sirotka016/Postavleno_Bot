from __future__ import annotations

import pytest

from postavleno_bot.utils.strings import mask_secret


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "—"),
        ("", "—"),
        ("1234567", "***"),
        ("1234567890", "12345…7890"),
        ("abcdefghijklmnopqrstuvwxyz", "abcde…wxyz"),
    ],
)
def test_mask_secret(value: str | None, expected: str) -> None:
    assert mask_secret(value) == expected

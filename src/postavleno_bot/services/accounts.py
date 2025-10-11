"""Account storage helpers."""

from __future__ import annotations

from functools import lru_cache

from ..core.config import get_settings
from ..repositories import (
    AccountAlreadyExistsError,
    AccountNotFoundError,
    AccountProfile,
    AccountsFSRepository,
)


@lru_cache
def get_accounts_repo() -> AccountsFSRepository:
    settings = get_settings()
    return AccountsFSRepository(settings.accounts_dir)


def delete_account(username: str) -> None:
    repo = get_accounts_repo()
    repo.delete(username)


__all__ = [
    "AccountAlreadyExistsError",
    "AccountNotFoundError",
    "AccountProfile",
    "get_accounts_repo",
    "delete_account",
]

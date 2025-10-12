"""Filesystem-based repository for user accounts."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import bcrypt

from ..core.logging import get_logger
from ..domain.validators import validate_login


@dataclass(slots=True)
class AccountProfile:
    """Account information stored on disk."""

    display_login: str
    username: str
    password_hash: str
    created_at: datetime
    company_name: str
    email: str | None
    wb_api: str | None
    ms_api: str | None

    @property
    def created_at_iso(self) -> str:
        return self.created_at.replace(microsecond=0).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "display_login": self.display_login,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at_iso,
            "company_name": self.company_name,
            "email": self.email,
            "wb_api": self.wb_api,
            "ms_api": self.ms_api,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AccountProfile:
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return cls(
            display_login=str(payload["display_login"]),
            username=str(payload["username"]),
            password_hash=str(payload["password_hash"]),
            created_at=created_at.astimezone(UTC),
            company_name=str(payload.get("company_name") or ""),
            email=payload.get("email"),
            wb_api=payload.get("wb_api"),
            ms_api=payload.get("ms_api"),
        )

    def with_updates(self, **fields: Any) -> AccountProfile:
        data = self.to_dict()
        data.update(fields)
        return AccountProfile.from_dict(data)


class AccountAlreadyExistsError(RuntimeError):
    """Raised when attempting to register an existing account."""


class AccountNotFoundError(RuntimeError):
    """Raised when an account is missing on disk."""


class AccountsFSRepository:
    """Persist accounts as JSON documents in the ``data/accounts`` directory."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._rounds = 12
        self._logger = get_logger(__name__).bind(repository="accounts_fs")

    def _account_dir(self, username: str) -> Path:
        return self._base_dir / username

    def _profile_path(self, username: str) -> Path:
        return self._account_dir(username) / "profile.json"

    def exists(self, username: str) -> bool:
        return self._profile_path(username).exists()

    def get(self, username: str) -> AccountProfile:
        path = self._profile_path(username)
        if not path.exists():
            raise AccountNotFoundError(username)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AccountProfile.from_dict(payload)

    def _write(self, profile: AccountProfile) -> None:
        path = self._profile_path(profile.username)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _hash_password(self, password: str) -> str:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=self._rounds))
        return hashed.decode("utf-8")

    def create(self, *, display_login: str, password: str) -> AccountProfile:
        username = display_login.lower()
        if not validate_login(display_login):
            raise ValueError("invalid login")
        if len(password) < 6:
            raise ValueError("password too short")
        if self.exists(username):
            raise AccountAlreadyExistsError(display_login)
        profile = AccountProfile(
            display_login=display_login,
            username=username,
            password_hash=self._hash_password(password),
            created_at=datetime.now(UTC),
            company_name=display_login,
            email=None,
            wb_api=None,
            ms_api=None,
        )
        self._write(profile)
        return profile

    def verify_password(self, profile: AccountProfile, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), profile.password_hash.encode("utf-8"))

    def set_password(self, username: str, password: str) -> AccountProfile:
        profile = self.get(username)
        updated = profile.with_updates(password_hash=self._hash_password(password))
        self._write(updated)
        return updated

    def set_email(self, username: str, email: str | None) -> AccountProfile:
        profile = self.get(username)
        updated = profile.with_updates(email=email)
        self._write(updated)
        return updated

    def set_wb_api(self, username: str, token: str | None) -> AccountProfile:
        profile = self.get(username)
        updated = profile.with_updates(wb_api=token)
        self._write(updated)
        return updated

    def set_ms_api(self, username: str, token: str | None) -> AccountProfile:
        profile = self.get(username)
        updated = profile.with_updates(ms_api=token)
        self._write(updated)
        return updated

    def set_company_name(self, username: str, company_name: str) -> AccountProfile:
        profile = self.get(username)
        updated = profile.with_updates(company_name=company_name)
        self._write(updated)
        return updated

    def delete(self, username: str) -> None:
        path = self._account_dir(username)
        if not path.exists():
            self._logger.warning(
                "Account directory missing during deletion",
                username=username,
                path=str(path),
            )
            return
        shutil.rmtree(path, ignore_errors=False)
        self._logger.info("Account directory removed", username=username, path=str(path))


__all__ = [
    "AccountProfile",
    "AccountAlreadyExistsError",
    "AccountNotFoundError",
    "AccountsFSRepository",
]

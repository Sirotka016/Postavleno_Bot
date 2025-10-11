from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from ..core.config import get_settings
from ..core.crypto import decrypt_json, encrypt_json


@dataclass(slots=True)
class UserProfile:
    login: str
    tg_user_id: int
    tg_name: str
    company: str
    email: str | None
    registered_at: datetime
    updated_at: datetime
    avatar_filename: str | None
    last_chat_id: int | None


@dataclass(slots=True)
class UserSecrets:
    password_hash: str
    wb_api: str | None
    ms_api: str | None


@dataclass(slots=True)
class UserData:
    profile: UserProfile
    secrets: UserSecrets


class UserStorageError(RuntimeError):
    """Base class for storage errors."""


class LoginAlreadyExistsError(UserStorageError):
    """Raised when attempting to register an existing login."""


class LoginNotFoundError(UserStorageError):
    """Raised when login is missing."""


class InvalidCredentialsError(UserStorageError):
    """Raised when password verification fails."""


class LoginOwnershipError(UserStorageError):
    """Raised when login belongs to another Telegram user."""


class FileUserStorage:
    """Store user data on disk using encrypted secrets."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._index_path = self._base_dir / "index.json"
        self._lock = asyncio.Lock()
        self._hasher = PasswordHasher()
        self._ensure_ready_sync()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _ensure_ready_sync(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._index_path.write_text("{}\n", encoding="utf-8")

    def _user_dir(self, login: str) -> Path:
        return self._base_dir / login

    def _profile_path(self, login: str) -> Path:
        return self._user_dir(login) / "profile.json"

    def _secrets_path(self, login: str) -> Path:
        return self._user_dir(login) / "secrets.json.enc"

    def _load_index_sync(self) -> dict[str, Any]:
        if not self._index_path.exists():
            return {}
        content = self._index_path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        return cast(dict[str, Any], json.loads(content))

    def _write_index_sync(self, index: dict[str, Any]) -> None:
        self._index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _profile_from_dict(self, payload: dict[str, Any]) -> UserProfile:
        return UserProfile(
            login=payload["login"],
            tg_user_id=int(payload["tg_user_id"]),
            tg_name=str(payload.get("tg_name", "")),
            company=str(payload.get("company", "")),
            email=payload.get("email"),
            registered_at=datetime.fromisoformat(payload["registered_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            avatar_filename=payload.get("avatar_filename"),
            last_chat_id=payload.get("last_chat_id"),
        )

    def _profile_to_dict(self, profile: UserProfile) -> dict[str, Any]:
        return {
            "login": profile.login,
            "tg_user_id": profile.tg_user_id,
            "tg_name": profile.tg_name,
            "company": profile.company,
            "email": profile.email,
            "registered_at": profile.registered_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
            "avatar_filename": profile.avatar_filename,
            "last_chat_id": profile.last_chat_id,
        }

    def _load_profile_sync(self, login: str) -> UserProfile:
        path = self._profile_path(login)
        if not path.exists():
            raise LoginNotFoundError(login)
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._profile_from_dict(data)

    def _write_profile_sync(self, profile: UserProfile) -> None:
        path = self._profile_path(profile.login)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._profile_to_dict(profile), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_secrets_sync(self, login: str) -> UserSecrets:
        path = self._secrets_path(login)
        if not path.exists():
            raise LoginNotFoundError(login)
        decrypted = decrypt_json(path.read_bytes())
        return UserSecrets(
            password_hash=str(decrypted["password_hash"]),
            wb_api=decrypted.get("wb_api"),
            ms_api=decrypted.get("ms_api"),
        )

    def _write_secrets_sync(self, login: str, secrets: UserSecrets) -> None:
        payload = {
            "password_hash": secrets.password_hash,
            "wb_api": secrets.wb_api,
            "ms_api": secrets.ms_api,
        }
        path = self._secrets_path(login)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encrypt_json(payload))

    def _load_user_sync(self, login: str) -> UserData:
        profile = self._load_profile_sync(login)
        secrets = self._load_secrets_sync(login)
        return UserData(profile=profile, secrets=secrets)

    def _update_index_entry(self, profile: UserProfile) -> None:
        index = self._load_index_sync()
        entry = index.get(profile.login, {})
        entry.update(
            {
                "tg_user_id": profile.tg_user_id,
                "registered_at": entry.get("registered_at", profile.registered_at.isoformat()),
                "updated_at": profile.updated_at.isoformat(),
                "tg_name": profile.tg_name,
                "last_chat_id": profile.last_chat_id,
            }
        )
        index[profile.login] = entry
        self._write_index_sync(index)

    def _register_user_sync(
        self,
        *,
        login: str,
        password: str,
        tg_user_id: int,
        tg_name: str,
        chat_id: int | None,
    ) -> UserData:
        index = self._load_index_sync()
        if login in index:
            raise LoginAlreadyExistsError(login)

        user_dir = self._user_dir(login)
        user_dir.mkdir(parents=True, exist_ok=True)
        now = self._now()
        profile = UserProfile(
            login=login,
            tg_user_id=tg_user_id,
            tg_name=tg_name,
            company=login,
            email=None,
            registered_at=now,
            updated_at=now,
            avatar_filename=None,
            last_chat_id=chat_id,
        )
        secrets = UserSecrets(
            password_hash=self._hasher.hash(password),
            wb_api=None,
            ms_api=None,
        )

        self._write_profile_sync(profile)
        self._write_secrets_sync(login, secrets)

        index[login] = {
            "tg_user_id": tg_user_id,
            "registered_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "tg_name": tg_name,
            "last_chat_id": chat_id,
        }
        self._write_index_sync(index)
        return UserData(profile=profile, secrets=secrets)

    async def register_user(
        self,
        *,
        login: str,
        password: str,
        tg_user_id: int,
        tg_name: str,
        chat_id: int | None,
    ) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(
                self._register_user_sync,
                login=login,
                password=password,
                tg_user_id=tg_user_id,
                tg_name=tg_name,
                chat_id=chat_id,
            )

    def _authenticate_user_sync(
        self,
        *,
        login: str,
        password: str,
        tg_user_id: int,
        tg_name: str,
        chat_id: int | None,
    ) -> UserData:
        index = self._load_index_sync()
        entry = index.get(login)
        if entry is None:
            raise LoginNotFoundError(login)
        owner_id = int(entry.get("tg_user_id", 0))
        if owner_id and owner_id != tg_user_id:
            raise LoginOwnershipError(login)

        user = self._load_user_sync(login)
        try:
            self._hasher.verify(user.secrets.password_hash, password)
        except VerifyMismatchError as exc:
            raise InvalidCredentialsError(login) from exc
        except InvalidHash as exc:  # pragma: no cover - corrupted data
            raise UserStorageError("Stored password hash is invalid") from exc

        if self._hasher.check_needs_rehash(user.secrets.password_hash):
            user.secrets = UserSecrets(
                password_hash=self._hasher.hash(password),
                wb_api=user.secrets.wb_api,
                ms_api=user.secrets.ms_api,
            )
            self._write_secrets_sync(login, user.secrets)

        now = self._now()
        user.profile.tg_user_id = tg_user_id
        user.profile.tg_name = tg_name
        user.profile.updated_at = now
        user.profile.last_chat_id = chat_id
        self._write_profile_sync(user.profile)

        index[login] = {
            "tg_user_id": tg_user_id,
            "registered_at": entry.get("registered_at", user.profile.registered_at.isoformat()),
            "updated_at": now.isoformat(),
            "tg_name": tg_name,
            "last_chat_id": chat_id,
        }
        self._write_index_sync(index)
        return self._load_user_sync(login)

    async def authenticate_user(
        self,
        *,
        login: str,
        password: str,
        tg_user_id: int,
        tg_name: str,
        chat_id: int | None,
    ) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(
                self._authenticate_user_sync,
                login=login,
                password=password,
                tg_user_id=tg_user_id,
                tg_name=tg_name,
                chat_id=chat_id,
            )

    async def is_login_taken(self, login: str) -> bool:
        async with self._lock:
            index = await asyncio.to_thread(self._load_index_sync)
        return login in index

    def _update_profile_field_sync(self, login: str, **fields: Any) -> UserData:
        user = self._load_user_sync(login)
        for key, value in fields.items():
            if hasattr(user.profile, key):
                setattr(user.profile, key, value)
        user.profile.updated_at = self._now()
        self._write_profile_sync(user.profile)
        self._update_index_entry(user.profile)
        return self._load_user_sync(login)

    async def update_company(self, login: str, company: str) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(self._update_profile_field_sync, login, company=company)

    async def update_email(self, login: str, email: str | None) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(self._update_profile_field_sync, login, email=email)

    def _update_secrets_sync(self, login: str, **fields: Any) -> UserData:
        user = self._load_user_sync(login)
        for key, value in fields.items():
            if hasattr(user.secrets, key):
                setattr(user.secrets, key, value)
        self._write_secrets_sync(login, user.secrets)
        user.profile.updated_at = self._now()
        self._write_profile_sync(user.profile)
        self._update_index_entry(user.profile)
        return self._load_user_sync(login)

    async def update_wb_key(self, login: str, value: str | None) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(self._update_secrets_sync, login, wb_api=value)

    async def update_ms_key(self, login: str, value: str | None) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(self._update_secrets_sync, login, ms_api=value)

    async def load_user(self, login: str) -> UserData:
        async with self._lock:
            return await asyncio.to_thread(self._load_user_sync, login)

    async def save_avatar(
        self, login: str, data: bytes, *, filename: str = "avatar.jpg"
    ) -> UserData:
        async with self._lock:
            user_dir = self._user_dir(login)
            path = user_dir / filename
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(path.write_bytes, data)
            return await asyncio.to_thread(
                self._update_profile_field_sync, login, avatar_filename=filename
            )


@lru_cache
def get_user_storage() -> FileUserStorage:
    settings = get_settings()
    base_dir = Path(settings.users_dir)
    storage = FileUserStorage(base_dir)
    return storage

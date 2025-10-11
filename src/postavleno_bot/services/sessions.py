"""Persistent session storage for chat authorizations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

try:  # pragma: no cover - optional dependency branch
    import orjson  # type: ignore
except Exception:  # pragma: no cover - graceful fallback when orjson is unavailable
    orjson = None  # type: ignore


def _json_dumps(data: dict[str, dict[str, str]]) -> bytes:
    if orjson is not None:
        return orjson.dumps(data, option=getattr(orjson, "OPT_INDENT_2", 0))  # type: ignore[arg-type]
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _json_loads(raw: bytes) -> dict[str, dict[str, str]]:
    loaded = orjson.loads(raw) if orjson is not None else json.loads(raw.decode("utf-8"))
    return dict(loaded)


class SessionStore:
    """Manage persistent chat sessions stored on disk."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path("data/sessions.json") if path is None else path
        self._lock = RLock()
        self._sessions: dict[int, dict[str, str]] = {}
        self.load()

    def load(self) -> None:
        """Load sessions from the JSON file if it exists."""

        with self._lock:
            if not self._path.exists():
                self._sessions = {}
                return
            try:
                raw = self._path.read_bytes()
            except FileNotFoundError:  # pragma: no cover - race condition guard
                self._sessions = {}
                return
            try:
                payload = _json_loads(raw)
            except Exception:  # pragma: no cover - corrupted file fallback
                self._sessions = {}
                return
            sessions: dict[int, dict[str, str]] = {}
            for key, value in payload.items():
                try:
                    chat_id = int(key)
                except (TypeError, ValueError):  # pragma: no cover - defensive branch
                    continue
                if not isinstance(value, dict):
                    continue
                username = value.get("username")
                since = value.get("since")
                if not isinstance(username, str):
                    continue
                if not isinstance(since, str):
                    since = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                sessions[chat_id] = {"username": username, "since": since}
            self._sessions = sessions

    def save(self) -> None:
        """Persist current sessions to disk."""

        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            serializable: dict[str, dict[str, str]] = {
                str(chat_id): mapping for chat_id, mapping in self._sessions.items()
            }
            self._path.write_bytes(_json_dumps(serializable))

    def get(self, chat_id: int) -> str | None:
        with self._lock:
            record = self._sessions.get(chat_id)
            return record.get("username") if record else None

    def set(self, chat_id: int, username: str) -> None:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._lock:
            existing = self._sessions.get(chat_id)
            if existing and existing.get("username") == username:
                if not isinstance(existing.get("since"), str):
                    existing["since"] = timestamp
                    self._sessions[chat_id] = existing
                    self.save()
                return
            self._sessions[chat_id] = {"username": username, "since": timestamp}
            self.save()

    def remove(self, chat_id: int) -> None:
        with self._lock:
            if chat_id in self._sessions:
                self._sessions.pop(chat_id, None)
                self.save()

    def is_authed(self, chat_id: int) -> bool:
        return self.get(chat_id) is not None


session_store = SessionStore()

__all__ = ["SessionStore", "session_store"]

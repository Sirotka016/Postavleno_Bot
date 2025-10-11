from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..core.config import get_settings
from ..core.logging import get_logger
from .models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_path(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    database_path = url.database
    if not database_path or database_path == ":memory:":
        return
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    _ensure_sqlite_path(settings.database_url)
    logger = get_logger(__name__).bind(action="db.init")
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    logger.info("Создано подключение к базе данных", outcome="ok")
    return engine


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        _engine = _create_engine()
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None  # pragma: no cover - for type checkers
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def create_all() -> None:
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

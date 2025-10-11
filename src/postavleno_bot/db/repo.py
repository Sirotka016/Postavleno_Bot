from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.crypto import encrypt_str
from .models import User

_UNSET = object()

TokenKind = Literal["tg_bot", "wb_api", "moysklad"]


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tg_user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.tg_user_id == tg_user_id))
        user: User | None = result.scalar_one_or_none()
        return user

    async def get_or_create(
        self,
        *,
        tg_user_id: int,
        chat_id: int | None,
        username: str | None,
    ) -> User:
        user = await self.get(tg_user_id)
        if user is None:
            user = User(
                tg_user_id=tg_user_id,
                chat_id=chat_id,
                username=username,
            )
            self._session.add(user)
            await self._session.commit()
            await self._session.refresh(user)
        else:
            updated = False
            if chat_id is not None and user.chat_id != chat_id:
                user.chat_id = chat_id
                updated = True
            if username != user.username:
                user.username = username
                updated = True
            if updated:
                await self._session.commit()
                await self._session.refresh(user)
        return user

    async def update_profile(
        self,
        user: User,
        *,
        display_name: str | None | object = _UNSET,
        company_name: str | None | object = _UNSET,
    ) -> User:
        if display_name is not _UNSET:
            user.display_name = display_name
        if company_name is not _UNSET:
            user.company_name = company_name
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def set_token(self, user: User, kind: TokenKind, token: str) -> User:
        encrypted = encrypt_str(token)
        if kind == "tg_bot":
            user.tg_bot_token_enc = encrypted
        elif kind == "wb_api":
            user.wb_api_token_enc = encrypted
        elif kind == "moysklad":
            user.moysklad_api_token_enc = encrypted
        else:  # pragma: no cover - defensive branch
            raise ValueError(f"Неизвестный тип токена: {kind}")

        was_registered = user.is_registered
        has_all_tokens = (
            user.tg_bot_token_enc is not None
            and user.wb_api_token_enc is not None
            and user.moysklad_api_token_enc is not None
        )
        if has_all_tokens and not was_registered:
            user.is_registered = True
            user.registered_at = datetime.utcnow()
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def replace_token(self, user: User, kind: TokenKind, token: str) -> User:
        return await self.set_token(user, kind, token)

    async def clear_tokens(self, user: User) -> User:
        user.tg_bot_token_enc = None
        user.wb_api_token_enc = None
        user.moysklad_api_token_enc = None
        user.is_registered = False
        user.registered_at = None
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

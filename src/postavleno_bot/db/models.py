from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, LargeBinary, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=lambda: datetime.utcnow(), nullable=False
    )

    tg_bot_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    wb_api_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    moysklad_api_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    avatar_emoji: Mapped[str] = mapped_column(String(8), default="👤", nullable=False)

    __table_args__ = (Index("ix_users_chat_id", "chat_id"),)


@event.listens_for(User, "before_insert", propagate=True)
def _set_updated_at_on_insert(mapper, connection, target: User) -> None:
    now = datetime.utcnow()
    if target.updated_at is None:
        target.updated_at = now


@event.listens_for(User, "before_update", propagate=True)
def _set_updated_at_on_update(mapper, connection, target: User) -> None:
    target.updated_at = datetime.utcnow()

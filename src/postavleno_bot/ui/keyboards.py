"""Inline keyboards used by the bot."""

from __future__ import annotations

from functools import lru_cache

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _build(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


@lru_cache(maxsize=None)
def kb_home(is_authed: bool) -> InlineKeyboardMarkup:
    if is_authed:
        rows = [
            [("👤 Профиль", "home.profile")],
            [("📊 Остатки WB (Общие)", "stocks_wb_all")],
            [("🏷️ Остатки WB (Склады)", "stocks_wb_bywh")],
            [("🔄 Обновить", "home.refresh")],
            [("✖️ Выйти", "home.exit")],
        ]
    else:
        rows = [
            [("🔐 Авторизация", "auth.login")],
            [("🆕 Регистрация", "auth.register")],
            [("🔄 Обновить", "home.refresh")],
            [("✖️ Выйти", "home.exit")],
        ]
    return _build(rows)


@lru_cache(maxsize=1)
def kb_auth_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🔐 Авторизация", "auth.login")],
            [("🆕 Регистрация", "auth.register")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_profile() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🏢 Компания", "profile.company")],
            [("✉️ Почта", "profile.email")],
            [("🔑 WB API", "profile.wb")],
            [("🚪 Выйти из профиля", "home.logout")],
            [("🗑️ Удалить аккаунт", "home.delete_open")],
            [("🔄 Обновить", "profile.refresh")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_company_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("✏️ Переименовать компанию", "company.rename")],
            [("🗑️ Удалить компанию", "company.delete")],
            [("🔄 Обновить", "company.refresh")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_company_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "company.delete.confirm")],
            [("Нет", "company.delete.cancel")],
        ]
    )


@lru_cache(maxsize=1)
def kb_wb_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("✏️ Изменить WB API", "wb.edit")],
            [("🗑️ Удалить WB API", "wb.delete")],
            [("🔄 Обновить", "wb.refresh")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_wb_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "wb.delete.confirm")],
            [("Нет", "wb.delete.cancel")],
        ]
    )


@lru_cache(maxsize=1)
def kb_export_missing_token() -> InlineKeyboardMarkup:
    return _build(
        [
            [("👤 Профиль", "home.profile")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_export_error() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_export_ready() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Удалить", "home.delete_confirm")],
            [("Отмена", "home.delete_cancel")],
        ]
    )


@lru_cache(maxsize=1)
def kb_delete_error() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "home.delete_cancel")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_edit_wb() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_edit_company() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_email_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("✏️ Изменить почту", "email.change")],
            [("🔗 Отвязать почту", "email.unlink")],
            [("🔄 Обновить", "email.refresh")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_email_unlink_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "email.unlink.confirm")],
            [("Нет", "email.unlink.cancel")],
        ]
    )


@lru_cache(maxsize=1)
def kb_edit_email() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_unknown() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🔁 Повторить", "unknown.repeat")],
            [("✖️ Выйти", "unknown.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_retry_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "login.retry")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_retry_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "register.retry")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


__all__ = [
    "kb_home",
    "kb_auth_menu",
    "kb_login",
    "kb_register",
    "kb_profile",
    "kb_company_menu",
    "kb_company_delete_confirm",
    "kb_wb_menu",
    "kb_wb_delete_confirm",
    "kb_export_missing_token",
    "kb_export_error",
    "kb_export_ready",
    "kb_delete_confirm",
    "kb_delete_error",
    "kb_edit_wb",
    "kb_edit_company",
    "kb_edit_email",
    "kb_email_menu",
    "kb_email_unlink_confirm",
    "kb_unknown",
    "kb_retry_login",
    "kb_retry_register",
]

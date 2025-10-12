"""Inline keyboard builders following the unified callback naming scheme."""

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


def _nav_rows(refresh_cb: str) -> list[list[tuple[str, str]]]:
    return [
        [("🔄 Обновить", refresh_cb)],
        [("◀️ Назад", "nav.back")],
        [("✖️ Выйти", "nav.exit")],
    ]


def kb_nav(refresh_cb: str) -> InlineKeyboardMarkup:
    return _build(_nav_rows(refresh_cb))


@lru_cache(maxsize=1)
def kb_auth_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🔐 Авторизация", "auth.login")],
            [("🆕 Регистрация", "auth.register")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


def kb_home(is_authed: bool) -> InlineKeyboardMarkup:
    if is_authed:
        rows = [
            [("👤 Профиль", "profile.open")],
            [("📊 Остатки WB (Общие)", "stocks_wb_all")],
            [("🏷️ Остатки WB (Склады)", "stocks_wb_bywh")],
            [("🔄 Обновить", "home.refresh")],
            [("✖️ Выйти", "nav.exit")],
        ]
    else:
        rows = [
            [("🔐 Авторизация", "auth.login")],
            [("🆕 Регистрация", "auth.register")],
            [("🔄 Обновить", "home.refresh")],
            [("✖️ Выйти", "nav.exit")],
        ]
    return _build(rows)


@lru_cache(maxsize=1)
def kb_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_profile() -> InlineKeyboardMarkup:
    rows = [
        [("📁 Компания", "company.open")],
        [("✉️ Почта", "email.open")],
        [("🔑 WB API", "wb.open")],
        [("📒 Выйти из профиля", "profile.logout")],
        [("🗑️ Удалить аккаунт", "profile.delete_confirm")],
    ]
    rows.extend(_nav_rows("profile.refresh"))
    return _build(rows)


def kb_company_menu() -> InlineKeyboardMarkup:
    rows = [
        [("✏️ Переименовать компанию", "company.rename")],
        [("🗑️ Удалить компанию", "company.delete_confirm")],
    ]
    rows.extend(_nav_rows("company.open"))
    return _build(rows)


def kb_email_menu() -> InlineKeyboardMarkup:
    rows = [
        [("✏️ Изменить почту", "email.change")],
        [("🔓 Отвязать почту", "email.unlink_confirm")],
    ]
    rows.extend(_nav_rows("email.open"))
    return _build(rows)


def kb_wb_menu() -> InlineKeyboardMarkup:
    rows = [
        [("✏️ Изменить WB API", "wb.change")],
        [("🗑️ Удалить WB API", "wb.delete_confirm")],
    ]
    rows.extend(_nav_rows("wb.open"))
    return _build(rows)


def kb_confirm(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", yes_cb)],
            [("Нет", no_cb)],
        ]
    )


def kb_export_missing_token() -> InlineKeyboardMarkup:
    return _build(
        [
            [("👤 Профиль", "profile.open")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


def kb_export_error() -> InlineKeyboardMarkup:
    rows = _nav_rows("home.refresh")
    return _build(rows)


def kb_export_ready() -> InlineKeyboardMarkup:
    rows = _nav_rows("home.refresh")
    return _build(rows)


def kb_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Удалить", "profile.delete_yes")],
            [("Отмена", "profile.delete_no")],
        ]
    )


def kb_delete_error() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "profile.delete_no")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_retry_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Попробовать ещё раз", "auth.login")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_retry_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Попробовать ещё раз", "auth.register")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


@lru_cache(maxsize=1)
def kb_unknown() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "nav.exit")],
        ]
    )


def kb_edit_company() -> InlineKeyboardMarkup:
    return _build(_nav_rows("company.ask_name"))


def kb_company_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "company.delete_yes")],
            [("Нет", "company.delete_no")],
        ]
    )


def kb_edit_email() -> InlineKeyboardMarkup:
    return _build(_nav_rows("email.open"))


def kb_email_unlink_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "email.unlink_yes")],
            [("Нет", "email.unlink_no")],
        ]
    )


def kb_edit_wb() -> InlineKeyboardMarkup:
    return _build(_nav_rows("wb.change"))


def kb_wb_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Да", "wb.delete_yes")],
            [("Нет", "wb.delete_no")],
        ]
    )


__all__ = [
    "kb_auth_menu",
    "kb_company_delete_confirm",
    "kb_company_menu",
    "kb_confirm",
    "kb_delete_confirm",
    "kb_delete_error",
    "kb_edit_company",
    "kb_edit_email",
    "kb_edit_wb",
    "kb_email_menu",
    "kb_email_unlink_confirm",
    "kb_export_error",
    "kb_export_missing_token",
    "kb_export_ready",
    "kb_home",
    "kb_login",
    "kb_nav",
    "kb_profile",
    "kb_register",
    "kb_retry_login",
    "kb_retry_register",
    "kb_unknown",
    "kb_wb_delete_confirm",
    "kb_wb_menu",
]

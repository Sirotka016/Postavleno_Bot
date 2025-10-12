"""Inline keyboards used by the bot."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _build(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


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


def kb_auth_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🔐 Авторизация", "auth.login")],
            [("🆕 Регистрация", "auth.register")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_profile() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🏢 Название компании", "profile.company")],
            [("🔑 WB API", "profile.wb")],
            [("✉️ Почта", "profile.email")],
            [("🗑️ Удалить аккаунт", "home.delete_open")],
            [("🔄 Обновить", "profile.refresh")],
            [("◀️ Назад", "nav.back")],
            [("📖 Выйти из профиля", "home.logout")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_export_missing_token() -> InlineKeyboardMarkup:
    return _build(
        [
            [("👤 Профиль", "home.profile")],
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_export_error() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_export_ready() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_delete_confirm() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Удалить", "home.delete_confirm")],
            [("Отмена", "home.delete_cancel")],
        ]
    )


def kb_delete_error() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "home.delete_cancel")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_edit_wb() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_edit_company() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_edit_email() -> InlineKeyboardMarkup:
    return _build(
        [
            [("◀️ Назад", "nav.back")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


def kb_unknown() -> InlineKeyboardMarkup:
    return _build(
        [
            [("🔁 Повторить", "unknown.repeat")],
            [("✖️ Выйти", "unknown.exit")],
        ]
    )


def kb_retry_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "login.retry")],
            [("✖️ Выйти", "home.exit")],
        ]
    )


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
    "kb_export_missing_token",
    "kb_export_error",
    "kb_export_ready",
    "kb_edit_wb",
    "kb_edit_company",
    "kb_edit_email",
    "kb_unknown",
    "kb_retry_login",
    "kb_retry_register",
]

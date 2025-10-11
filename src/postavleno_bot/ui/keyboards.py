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


def kb_home() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Авторизация", "home.auth")],
            [("Обновить", "home.refresh")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_auth_menu() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Авторизация", "auth.login")],
            [("Регистрация", "auth.register")],
            [("Обновить", "auth.refresh")],
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_profile() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Сменить WB API", "profile.wb")],
            [("Сменить «Мой Склад» API", "profile.ms")],
            [("Сменить Почту", "profile.email")],
            [("Обновить", "profile.refresh")],
            [("Назад", "nav.back")],
            [("Выйти с Профиля", "profile.logout")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_edit_wb() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_edit_ms() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_edit_email() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Назад", "nav.back")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_unknown() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "unknown.repeat")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_retry_login() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "login.retry")],
            [("Выйти", "home.exit")],
        ]
    )


def kb_retry_register() -> InlineKeyboardMarkup:
    return _build(
        [
            [("Повторить", "register.retry")],
            [("Выйти", "home.exit")],
        ]
    )


__all__ = [
    "kb_home",
    "kb_auth_menu",
    "kb_login",
    "kb_register",
    "kb_profile",
    "kb_edit_wb",
    "kb_edit_ms",
    "kb_edit_email",
    "kb_unknown",
    "kb_retry_login",
    "kb_retry_register",
]

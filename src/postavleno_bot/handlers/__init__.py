"""Aggregate router for all bot handlers."""

from __future__ import annotations

from aiogram import Router

from . import auth_menu, fallback, home, login, navigation, profile, register

router = Router(name="postavleno")
router.include_router(home.router)
router.include_router(auth_menu.router)
router.include_router(login.router)
router.include_router(register.router)
router.include_router(profile.router)
router.include_router(navigation.router)
router.include_router(fallback.router)

__all__ = ["router"]

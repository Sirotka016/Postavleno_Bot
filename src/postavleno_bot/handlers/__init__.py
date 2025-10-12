"""Aggregate router for all bot handlers."""

from __future__ import annotations

from aiogram import Router

from . import (
    auth_menu,
    cb_help_ok,
    cmd_help,
    company,
    email,
    fallback,
    home,
    login,
    menu,
    navigation,
    profile,
    register,
    wb,
)

router = Router(name="postavleno")
router.include_router(home.router)
router.include_router(auth_menu.router)
router.include_router(login.router)
router.include_router(register.router)
router.include_router(profile.router)
router.include_router(company.router)
router.include_router(email.router)
router.include_router(wb.router)
router.include_router(menu.router)
router.include_router(cmd_help.router)
router.include_router(cb_help_ok.router)
router.include_router(navigation.router)
router.include_router(fallback.router)

__all__ = ["router"]

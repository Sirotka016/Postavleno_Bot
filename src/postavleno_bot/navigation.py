"""Navigation helpers backed by FSM storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiogram.fsm.context import FSMContext

NAV_STACK_KEY = "nav_stack"
CURRENT_SCREEN_KEY = "current_screen"


@dataclass(slots=True)
class ScreenState:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


async def _load_stack(state: FSMContext) -> list[ScreenState]:
    data = await state.get_data()
    raw_stack = data.get(NAV_STACK_KEY, [])
    stack: list[ScreenState] = []
    for item in raw_stack:
        if isinstance(item, dict) and "name" in item:
            params = item.get("params") or {}
            stack.append(ScreenState(name=str(item["name"]), params=dict(params)))
    return stack


async def _store_stack(state: FSMContext, stack: list[ScreenState]) -> None:
    await state.update_data(
        **{
            NAV_STACK_KEY: [
                {"name": screen.name, "params": dict(screen.params)} for screen in stack
            ],
            CURRENT_SCREEN_KEY: stack[-1].name if stack else None,
        }
    )


async def nav_push(state: FSMContext, screen: ScreenState) -> None:
    stack = await _load_stack(state)
    stack.append(screen)
    await _store_stack(state, stack)


async def nav_replace(state: FSMContext, screen: ScreenState) -> None:
    stack = await _load_stack(state)
    if stack:
        stack[-1] = screen
    else:
        stack.append(screen)
    await _store_stack(state, stack)


async def nav_root(state: FSMContext, screen: ScreenState) -> None:
    await _store_stack(state, [screen])


async def nav_back(state: FSMContext) -> ScreenState | None:
    stack = await _load_stack(state)
    if len(stack) <= 1:
        return stack[-1] if stack else None
    stack.pop()
    await _store_stack(state, stack)
    return stack[-1]


async def current_screen(state: FSMContext) -> ScreenState | None:
    stack = await _load_stack(state)
    return stack[-1] if stack else None


SCREEN_HOME = "HOME"
SCREEN_AUTH_MENU = "AUTH_MENU"
SCREEN_LOGIN = "LOGIN"
SCREEN_REGISTER = "REGISTER"
SCREEN_PROFILE = "PROFILE"
SCREEN_EDIT_COMPANY = "EDIT_COMPANY"
SCREEN_EDIT_WB = "EDIT_WB_API"
SCREEN_EDIT_MS = "EDIT_MS_API"
SCREEN_EDIT_EMAIL = "EDIT_EMAIL"
SCREEN_UNKNOWN = "UNKNOWN"
SCREEN_DELETE_CONFIRM = "DELETE_CONFIRM"
SCREEN_EXPORT_STATUS = "EXPORT_STATUS"
SCREEN_EXPORT_DONE = "EXPORT_DONE"


__all__ = [
    "ScreenState",
    "nav_push",
    "nav_replace",
    "nav_root",
    "nav_back",
    "current_screen",
    "SCREEN_HOME",
    "SCREEN_AUTH_MENU",
    "SCREEN_LOGIN",
    "SCREEN_REGISTER",
    "SCREEN_PROFILE",
    "SCREEN_EDIT_COMPANY",
    "SCREEN_EDIT_WB",
    "SCREEN_EDIT_MS",
    "SCREEN_EDIT_EMAIL",
    "SCREEN_UNKNOWN",
    "SCREEN_DELETE_CONFIRM",
    "SCREEN_EXPORT_STATUS",
    "SCREEN_EXPORT_DONE",
]

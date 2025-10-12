"""Registry for help command profile steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ProfileStep:
    unauthorized: str
    authorized: str
    enabled: bool = True


_PROFILE_STEPS: list[ProfileStep] = [
    ProfileStep(
        unauthorized="   — «Компания» — укажите название (можно изменить позже).",
        authorized="   — «Компания» — укажите/измените название.",
    ),
    ProfileStep(
        unauthorized="   — «Почта» — привяжите и подтвердите email (на него придёт код).",
        authorized="   — «Почта» — привяжите и подтвердите email (на него придёт код).",
    ),
    ProfileStep(
        unauthorized="   — «WB API» — добавьте ключ из кабинета WB (Доступ к API).",
        authorized="   — «WB API» — добавьте или обновите ключ из кабинета WB (Доступ к API).",
    ),
]


def profile_step_lines(*, authorized: bool) -> List[str]:
    return [
        (step.authorized if authorized else step.unauthorized)
        for step in _PROFILE_STEPS
        if step.enabled
    ]


__all__ = ["ProfileStep", "profile_step_lines"]

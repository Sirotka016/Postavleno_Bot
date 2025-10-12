"""Registry of abilities highlighted on the home screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Ability:
    lines: tuple[str, ...]
    enabled: bool = True


_REGISTRY: list[Ability] = [
    Ability(
        lines=(
            "• Выгружаю остатки Wildberries двумя способами:",
            "  — «Остатки WB (Общие)» — одна строка на артикул, всё суммировано.",
            "  — «Остатки WB (Склады)» — разрез по складам.",
        ),
    ),
    Ability(
        lines=("• Помогаю настроить профиль: Компания, Почта, ключ WB API.",),
    ),
]


def ability_lines() -> List[str]:
    return [line for ability in _REGISTRY if ability.enabled for line in ability.lines]


__all__ = ["ability_lines", "Ability"]

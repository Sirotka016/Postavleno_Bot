from __future__ import annotations

from postavleno_bot.handlers.menu import inline_controls


def test_inline_controls_has_two_buttons() -> None:
    kb = inline_controls()
    row = kb.inline_keyboard[0]
    assert [b.text for b in row] == ["🔄 Обновить", "🚪 Выйти"]
    assert [b.callback_data for b in row] == ["refresh_menu", "exit_menu"]

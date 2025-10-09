from __future__ import annotations

from postavleno_bot.handlers.menu import inline_controls


def test_inline_controls_has_two_buttons() -> None:
    kb = inline_controls()
    assert [b.text for b in kb.inline_keyboard[0]] == ["📦 Остатки WB"]
    assert [b.callback_data for b in kb.inline_keyboard[0]] == ["main.stocks"]
    assert [b.text for b in kb.inline_keyboard[1]] == ["🔄 Обновить", "🚪 Выйти"]
    assert [b.callback_data for b in kb.inline_keyboard[1]] == ["main.refresh", "main.exit"]

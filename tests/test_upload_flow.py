from __future__ import annotations

import pandas as pd

from postavleno_bot.handlers.menu import (
    build_local_result_text,
    build_local_upload_keyboard,
    build_local_upload_text,
)
from postavleno_bot.services.local import build_local_preview, merge_wb_with_local


def test_upload_button_hidden_while_waiting() -> None:
    keyboard = build_local_upload_keyboard(ready=False)

    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

    assert all("📤" not in text for text in button_texts)
    assert any(text == "🔄 Обновить" for text in button_texts)
    assert any(text == "⬅️ Назад" for text in button_texts)


def test_both_files_trigger_merge_and_result() -> None:
    wb_df = pd.DataFrame({"supplierArticle": ["sku-1", "sku-2"], "quantity": [10, 5]})
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-2"], "Количество": [3, 4]})

    merged, stats = merge_wb_with_local(wb_df, local_df, store_name="FootballShop")

    upload_text = build_local_upload_text(
        wb_uploaded=True,
        local_uploaded=True,
        stats=None,
        message=None,
    )

    assert "✅ Файл Wildberries" in upload_text
    assert "✅ Файл склада" in upload_text

    preview_lines, total = build_local_preview(merged)
    result_text = build_local_result_text(stats, preview_lines, total)

    assert "✅ Итог готов" in result_text
    assert f"• Строк в файле WB: {stats.wb_rows}" in result_text
    assert f"• Совпадений по артикулу: {stats.matched_rows}" in result_text
    assert "Склад=FootballShop" in result_text


def test_unknown_file_gives_human_message() -> None:
    message = "Не узнаю формат. Нужны столбцы Артикул и Количество."

    upload_text = build_local_upload_text(
        wb_uploaded=False,
        local_uploaded=False,
        stats=None,
        message=message,
    )

    assert message in upload_text
    assert upload_text.endswith(message)

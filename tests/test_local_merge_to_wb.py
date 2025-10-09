from __future__ import annotations

import os

import pandas as pd

from postavleno_bot.core.config import get_settings
from postavleno_bot.handlers.menu import build_local_export_text, build_local_upload_text
from postavleno_bot.services.local import build_local_preview, merge_wb_with_local
from postavleno_bot.state.session import ChatSession, ScreenState, nav_back, nav_push, nav_replace


def _make_wb_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "supplierArticle": ["sku-1", "sku-1", "sku-2"],
            "quantity": [10, 5, 7],
            "brand": ["BrandA", "BrandA", "BrandB"],
            "subject": ["Футболки", "Футболки", "Обувь"],
            "techSize": ["M", "M", "42"],
            "barcode": ["111", "111", "222"],
            "category": ["Одежда", "Одежда", "Обувь"],
            "price": [1000, 1000, 2000],
            "discount": [10, 10, 15],
        }
    )


def _make_local_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Артикул": ["sku-1", "sku-3"],
            "Количество": [4, 8],
        }
    )


def test_wb_dedup_by_article() -> None:
    wb_df = _make_wb_dataframe()
    local_df = _make_local_dataframe()

    result, stats = merge_wb_with_local(wb_df, local_df, store_name="FootballShop")

    assert result["Артикул"].is_unique
    assert stats.wb_rows == 3
    assert stats.wb_unique == 2


def test_merge_replaces_local_qty_only_for_matched() -> None:
    wb_df = pd.DataFrame({"supplierArticle": ["sku-1", "sku-2"], "quantity": [5, 9]})
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-3"], "Количество": [3, 7]})

    result, stats = merge_wb_with_local(wb_df, local_df, store_name="FootballShop")

    sku1_qty = result.loc[result["Артикул"] == "SKU-1", "Кол-во_наш_склад"].iloc[0]
    sku2_qty = result.loc[result["Артикул"] == "SKU-2", "Кол-во_наш_склад"].iloc[0]

    assert sku1_qty == 3
    assert sku2_qty == 0
    assert stats.matched_rows == 1
    assert set(result["Артикул"]) == {"SKU-1", "SKU-2"}


def test_result_columns_and_store_name() -> None:
    store_name = "MyLocalStore"
    wb_df = _make_wb_dataframe()
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-2"], "Количество": [5, 2]})

    result, _ = merge_wb_with_local(wb_df, local_df, store_name=store_name)

    expected_columns = [
        "Склад",
        "Артикул",
        "nmId",
        "Штрихкод",
        "Кол-во_наш_склад",
        "Категория",
        "Предмет",
        "Бренд",
        "Размер",
        "Цена",
        "Скидка",
    ]
    assert list(result.columns) == expected_columns
    assert set(result["Склад"]) == {store_name}


def test_upload_flow_marks_and_result_transition() -> None:
    store_name = "FootballShop"
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "TEST:TOKEN")
    os.environ["LOCAL_STORE_NAME"] = store_name
    get_settings.cache_clear()
    wb_df = _make_wb_dataframe()
    local_df = pd.DataFrame({"Артикул": ["sku-1", "sku-2"], "Количество": [5, 6]})
    result_df, stats = merge_wb_with_local(wb_df, local_df, store_name=store_name)

    upload_text_after_wb = build_local_upload_text(
        wb_uploaded=True,
        local_uploaded=False,
        stats=None,
        message=None,
    )
    assert "✅ Файл Wildberries" in upload_text_after_wb
    assert "⬜ Файл склада" in upload_text_after_wb

    upload_text_after_both = build_local_upload_text(
        wb_uploaded=True,
        local_uploaded=True,
        stats=stats,
        message=None,
    )
    assert "✅ Файл Wildberries" in upload_text_after_both
    assert "✅ Файл склада" in upload_text_after_both
    assert f"Уникальных артикулов WB: {stats.wb_unique}" in upload_text_after_both

    preview_lines, total = build_local_preview(result_df)
    summary_lines = [
        "✅ Оба файла загружены. Итог готов.",
        f"• Уникальных артикулов WB: {stats.wb_unique}",
        f"• Совпадений с локальным складом: {stats.matched_rows}",
        "• Колонки: "
        f"Склад={store_name}, Артикул, nmId, Штрихкод, Кол-во_наш_склад, Категория, Предмет, Бренд, Размер, Цена, Скидка",
    ]
    result_text = build_local_export_text(summary_lines, preview_lines, total)

    assert "🏭 Остатки склада — итог" in result_text
    assert "Первые позиции" in result_text
    assert summary_lines[0] in result_text


def test_back_navigates_previous_screen() -> None:
    session = ChatSession()
    nav_push(session, ScreenState(name="LOCAL_OPEN", params={}))
    nav_push(session, ScreenState(name="LOCAL_UPLOAD", params={}))
    nav_replace(session, ScreenState(name="LOCAL_VIEW", params={}))

    current = session.history[-1]
    previous = nav_back(session)
    if current.name == "LOCAL_VIEW":
        nav_push(session, ScreenState(name="LOCAL_UPLOAD", params={}))

    assert previous is not None
    assert previous.name == "LOCAL_OPEN"
    assert session.history[-1].name == "LOCAL_UPLOAD"

import pandas as pd

from postavleno_bot.services.exports import wb_to_df_all, wb_to_df_bywh


def test_wb_all_aggregation_no_duplicates() -> None:
    payload = [
        {
            "supplierArticle": "A",
            "nmId": 1,
            "barcode": "b1",
            "quantity": 2,
            "inWayToClient": 1,
            "inWayFromClient": 0,
            "quantityFull": 3,
            "warehouseName": "MSK",
        },
        {
            "supplierArticle": "A",
            "nmId": 1,
            "barcode": "b1",
            "quantity": 3,
            "inWayToClient": 0,
            "inWayFromClient": 1,
            "quantityFull": 4,
            "warehouseName": "SPB",
        },
    ]
    df = wb_to_df_all(payload)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "Артикул поставщика",
        "nmId",
        "Штрихкод",
        "Кол-во",
        "В пути к клиенту",
        "Возврат от клиента",
        "Итого",
    ]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Артикул поставщика"] == "A"
    assert row["nmId"] == 1
    assert row["Штрихкод"] == "b1"
    assert row["Кол-во"] == 5
    assert row["В пути к клиенту"] == 1
    assert row["Возврат от клиента"] == 1
    assert row["Итого"] == 7


def test_wb_all_groups_by_article_and_nm() -> None:
    payload = [
        {
            "supplierArticle": "B",
            "nmId": 10,
            "barcode": "x1",
            "quantity": 1,
            "inWayToClient": 0,
            "inWayFromClient": 0,
            "quantityFull": 1,
        },
        {
            "supplierArticle": "B",
            "nmId": 11,
            "barcode": "x2",
            "quantity": 2,
            "inWayToClient": 0,
            "inWayFromClient": 0,
            "quantityFull": 2,
        },
        {
            "supplierArticle": "B",
            "nmId": 11,
            "barcode": "x2",
            "quantity": 3,
            "inWayToClient": 1,
            "inWayFromClient": 0,
            "quantityFull": 4,
        },
    ]
    df = wb_to_df_all(payload)
    assert len(df) == 2
    first = df[df["nmId"] == 10].iloc[0]
    second = df[df["nmId"] == 11].iloc[0]
    assert first["Артикул поставщика"] == "B"
    assert first["Штрихкод"] == "x1"
    assert first["Кол-во"] == 1
    assert second["Кол-во"] == 5
    assert second["Штрихкод"] == "x2"


def test_wb_all_uses_first_nonempty_barcode() -> None:
    payload = [
        {
            "supplierArticle": "C",
            "nmId": 42,
            "barcode": "",
            "quantity": 1,
            "inWayToClient": 0,
            "inWayFromClient": 0,
            "quantityFull": 1,
        },
        {
            "supplierArticle": "C",
            "nmId": 42,
            "barcode": "",
            "quantity": 2,
            "inWayToClient": 0,
            "inWayFromClient": 0,
            "quantityFull": 2,
        },
        {
            "supplierArticle": "C",
            "nmId": 42,
            "barcode": "BR-123",
            "quantity": 3,
            "inWayToClient": 1,
            "inWayFromClient": 0,
            "quantityFull": 4,
        },
    ]
    df = wb_to_df_all(payload)
    row = df.iloc[0]
    assert row["Штрихкод"] == "BR-123"
    assert row["Кол-во"] == 6
    assert row["Итого"] == 7


def test_wb_bywh_headers_and_order() -> None:
    payload = [
        {
            "warehouseName": "Москва",
            "supplierArticle": "ART-1",
            "nmId": 100,
            "barcode": "123",
            "quantity": 5,
            "inWayToClient": 1,
            "inWayFromClient": 0,
            "quantityFull": 6,
        },
        {
            "warehouseName": "Санкт-Петербург",
            "supplierArticle": "ART-1",
            "nmId": 100,
            "barcode": "123",
            "quantity": 1,
            "inWayToClient": 0,
            "inWayFromClient": 0,
            "quantityFull": 1,
        },
    ]
    df = wb_to_df_bywh(payload)
    assert list(df.columns) == [
        "Город склада",
        "Артикул поставщика",
        "nmId",
        "Штрихкод",
        "Кол-во",
        "В пути к клиенту",
        "Возврат от клиента",
        "Итого",
    ]
    assert list(df["Город склада"]) == ["Москва", "Санкт-Петербург"]

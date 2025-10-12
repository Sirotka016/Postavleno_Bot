import pandas as pd

from postavleno_bot.services.exports import wb_to_df_all_agg


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
    df = wb_to_df_all_agg(payload)
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

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from ..core.config import get_settings
from .export import dataframe_to_xlsx_bytes

LOCAL_DATA_DIR = Path("data/local")


@dataclass(slots=True)
class LocalJoinStats:
    wb_rows: int
    wb_unique: int
    local_rows: int
    matched_rows: int


class LocalFileError(RuntimeError):
    """Raised when a local stock file cannot be processed."""


def ensure_local_dir(chat_id: int) -> Path:
    directory = LOCAL_DATA_DIR / str(chat_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize_name(name: str) -> str:
    normalized = str(name).strip().lower().replace("\xa0", " ")
    normalized = re.sub(r"[\s\-–—]+", "_", normalized)
    normalized = re.sub(r"__+", "_", normalized)
    return normalized.strip("_")


COLUMN_ALIASES: dict[str, str] = {
    "supplierarticle": "supplierArticle",
    "артикул": "supplierArticle",
    "артикул_поставщика": "supplierArticle",
    "article": "supplierArticle",
    "nm": "nmId",
    "nm_id": "nmId",
    "nmid": "nmId",
    "nm id": "nmId",
    "warehousename": "warehouseName",
    "warehouse": "warehouseName",
    "склад": "warehouseName",
    "quantity": "quantity",
    "количество": "quantity",
    "кол_во": "quantity",
    "кол-во": "quantity",
    "qty": "quantity",
    "остаток": "quantity",
    "barcode": "barcode",
    "штрихкод": "barcode",
    "brand": "brand",
    "бренд": "brand",
    "subject": "subject",
    "предмет": "subject",
    "techsize": "techSize",
    "tech_size": "techSize",
    "размер": "techSize",
    "category": "category",
    "категория": "category",
    "price": "price",
    "цена": "price",
    "discount": "discount",
    "скидка": "discount",
}

WB_HINT_COLUMNS = {
    "warehouseName",
    "nmId",
    "subject",
    "brand",
    "techSize",
    "barcode",
    "category",
    "price",
    "discount",
}


def rename_known_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    seen: set[str] = set()
    for column in df.columns:
        normalized = _normalize_name(column)
        canonical = COLUMN_ALIASES.get(normalized)
        if canonical and canonical not in seen:
            rename_map[column] = canonical
            seen.add(canonical)
    return df.rename(columns=rename_map)


def classify_dataframe(df: pd.DataFrame) -> str | None:
    normalized = rename_known_columns(df.copy())
    columns = set(normalized.columns)

    if "supplierArticle" not in columns or "quantity" not in columns:
        return None

    if columns & WB_HINT_COLUMNS:
        return "WB"

    return "LOCAL"


def dataframe_from_bytes(data: bytes, filename: str | None) -> pd.DataFrame:
    suffix = Path(filename or "").suffix.lower()

    if suffix == ".csv":
        return _read_csv(data)

    readers: list[tuple[str | None, dict[str, object]]] = []
    if suffix == ".xlsx":
        readers.append(("openpyxl", {}))
    elif suffix == ".xls":
        readers.append(("xlrd", {}))
    else:
        readers.append((None, {}))

    readers.append((None, {}))

    for engine, options in readers:
        try:
            return pd.read_excel(BytesIO(data), engine=engine, **options)
        except Exception:
            continue

    try:
        return _read_csv(data)
    except Exception as csv_exc:  # pragma: no cover - propagate details
        raise LocalFileError("Не удалось прочитать файл как Excel или CSV") from csv_exc


def _read_csv(data: bytes) -> pd.DataFrame:
    buffer = BytesIO(data)
    try:
        buffer.seek(0)
        return pd.read_csv(buffer, sep=None, engine="python", encoding="utf-8-sig")
    except Exception:
        pass

    for sep in (",", ";", "\t"):
        try:
            buffer.seek(0)
            return pd.read_csv(buffer, sep=sep, encoding="utf-8-sig")
        except Exception:
            continue
    raise LocalFileError("Не удалось прочитать CSV-файл")


def _prepare_wb_unique(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    normalized = rename_known_columns(df.copy())
    required = {"supplierArticle", "quantity"}
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise LocalFileError("Не узнаю формат WB. Нужны столбцы Артикул и Количество.")

    normalized["supplierArticle"] = normalized["supplierArticle"].astype(str).str.strip()
    normalized = normalized[normalized["supplierArticle"] != ""]
    total_rows = len(normalized)

    normalized["ART"] = normalized["supplierArticle"].str.upper()

    deduped = normalized.drop_duplicates(subset=["ART"], keep="first").reset_index(drop=True)
    unique_rows = len(deduped)

    result = pd.DataFrame({"ART": deduped["ART"]})

    if "nmId" in deduped.columns:
        result["nmId"] = pd.to_numeric(deduped["nmId"], errors="coerce").astype("Int64")
    else:
        result["nmId"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    for column in ("barcode", "brand", "subject", "techSize", "category"):
        if column in deduped.columns:
            result[column] = deduped[column].where(deduped[column].notna(), None)
        else:
            result[column] = pd.Series([None] * unique_rows, dtype="object")

    if "price" in deduped.columns:
        result["price"] = pd.to_numeric(deduped["price"], errors="coerce").astype("Int64")
    else:
        result["price"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    if "discount" in deduped.columns:
        result["discount"] = pd.to_numeric(deduped["discount"], errors="coerce").astype("Int64")
    else:
        result["discount"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    return result, total_rows, unique_rows


def _prepare_local_aggregated(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    normalized = rename_known_columns(df.copy())
    required = {"supplierArticle", "quantity"}
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise LocalFileError("Не узнаю формат склада. Нужны столбцы Артикул и Количество.")

    normalized["supplierArticle"] = normalized["supplierArticle"].astype(str).str.strip()
    normalized = normalized[normalized["supplierArticle"] != ""]
    normalized["ART"] = normalized["supplierArticle"].str.upper()
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce").fillna(0)

    total_rows = len(normalized)

    aggregated = normalized.groupby("ART", as_index=False)["quantity"].sum()
    aggregated["quantity"] = aggregated["quantity"].round().astype(int)
    aggregated = aggregated.rename(columns={"quantity": "qty_local"})
    return aggregated, total_rows


def merge_wb_with_local(
    wb_df: pd.DataFrame,
    local_df: pd.DataFrame,
    *,
    store_name: str | None = None,
) -> tuple[pd.DataFrame, LocalJoinStats]:
    wb_unique, wb_rows, wb_unique_count = _prepare_wb_unique(wb_df)
    local_sum, local_rows = _prepare_local_aggregated(local_df)

    merged = wb_unique.merge(local_sum, how="left", on="ART")
    matched_mask = merged["qty_local"].notna()
    matched_rows = int(matched_mask.sum())
    merged["qty_local"] = merged["qty_local"].fillna(0).astype(int)

    warehouse = store_name or get_settings().local_store_name

    result = pd.DataFrame(
        {
            "Склад": warehouse,
            "Артикул": merged["ART"],
            "nmId": merged["nmId"],
            "Штрихкод": merged["barcode"],
            "Кол-во_наш_склад": merged["qty_local"],
            "Категория": merged["category"],
            "Предмет": merged["subject"],
            "Бренд": merged["brand"],
            "Размер": merged["techSize"],
            "Цена": merged["price"],
            "Скидка": merged["discount"],
        }
    )

    result = result.sort_values("Артикул").reset_index(drop=True)

    stats = LocalJoinStats(
        wb_rows=wb_rows,
        wb_unique=wb_unique_count,
        local_rows=local_rows,
        matched_rows=matched_rows,
    )
    return result, stats


def save_wb_upload(chat_id: int, df: pd.DataFrame) -> Path:
    directory = ensure_local_dir(chat_id)
    normalized = rename_known_columns(df.copy())
    timestamp = _timestamp()
    payload = dataframe_to_xlsx_bytes(normalized)

    latest_path = directory / "wb.xlsx"
    latest_path.write_bytes(payload)
    (directory / f"wb_{timestamp}.xlsx").write_bytes(payload)
    return latest_path


def save_local_upload(chat_id: int, df: pd.DataFrame) -> Path:
    directory = ensure_local_dir(chat_id)
    normalized = rename_known_columns(df.copy())
    timestamp = _timestamp()
    payload = dataframe_to_xlsx_bytes(normalized)

    latest_path = directory / "local.xlsx"
    latest_path.write_bytes(payload)
    (directory / f"local_{timestamp}.xlsx").write_bytes(payload)
    return latest_path


def save_result(chat_id: int, df: pd.DataFrame) -> Path:
    directory = ensure_local_dir(chat_id)
    timestamp = _timestamp()
    store_name = get_settings().local_store_name
    payload = dataframe_to_xlsx_bytes(df, sheet_name=store_name)

    latest_path = directory / "result.xlsx"
    latest_path.write_bytes(payload)
    timestamp_path = directory / f"result_{timestamp}.xlsx"
    timestamp_path.write_bytes(payload)
    return timestamp_path


def load_latest(chat_id: int, kind: str) -> pd.DataFrame | None:
    directory = ensure_local_dir(chat_id)
    path = directory / f"{kind}.xlsx"
    if not path.exists():
        return None
    return pd.read_excel(path)


def build_local_preview(df: pd.DataFrame, *, limit: int = 25) -> tuple[list[str], int]:
    total = len(df)
    subset = df.head(limit)
    lines = [f"• {row['Артикул']} — {row['Кол-во_наш_склад']}" for _, row in subset.iterrows()]
    return lines, total


def recompute_local_result(chat_id: int) -> tuple[pd.DataFrame, LocalJoinStats, Path] | None:
    wb_df = load_latest(chat_id, "wb")
    local_df = load_latest(chat_id, "local")
    if wb_df is None or local_df is None:
        return None

    result_df, stats = merge_wb_with_local(wb_df, local_df)
    result_path = save_result(chat_id, result_df)
    return result_df, stats, result_path


def build_local_only_dataframe(chat_id: int) -> pd.DataFrame | None:
    local_df = load_latest(chat_id, "local")
    if local_df is None:
        return None
    aggregated, _ = _prepare_local_aggregated(local_df)
    return aggregated.rename(columns={"ART": "Артикул", "qty_local": "Количество"})

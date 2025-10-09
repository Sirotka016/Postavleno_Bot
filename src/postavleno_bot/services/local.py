from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from .export import dataframe_to_xlsx_bytes

LOCAL_DATA_DIR = Path("data/local")


@dataclass(slots=True)
class LocalJoinStats:
    wb_count: int
    matched: int
    dropped: int


class LocalFileError(RuntimeError):
    """Raised when a local stock file cannot be processed."""


def ensure_local_dir(chat_id: int) -> Path:
    directory = LOCAL_DATA_DIR / str(chat_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize_name(name: str) -> str:
    return name.strip().lower()


COLUMN_ALIASES: dict[str, str] = {
    "supplierarticle": "supplierArticle",
    "артикул": "supplierArticle",
    "article": "supplierArticle",
    "nm": "nmId",
    "nm id": "nmId",
    "nm_id": "nmId",
    "nmid": "nmId",
    "warehousename": "warehouseName",
    "warehouse": "warehouseName",
    "склад": "warehouseName",
    "quantity": "quantity",
    "количество": "quantity",
    "кол-во": "quantity",
    "остаток": "quantity",
}


def rename_known_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    seen: set[str] = set()
    for column in df.columns:
        normalized = _normalize_name(str(column))
        canonical = COLUMN_ALIASES.get(normalized)
        if canonical and canonical not in seen:
            rename_map[column] = canonical
            seen.add(canonical)
    return df.rename(columns=rename_map)


def classify_dataframe(df: pd.DataFrame) -> str | None:
    normalized = rename_known_columns(df.copy())
    columns = set(normalized.columns)

    has_supplier = "supplierArticle" in columns
    has_nm = "nmId" in columns
    has_warehouse = "warehouseName" in columns
    has_quantity = "quantity" in columns

    if has_supplier and has_nm and has_warehouse and has_quantity:
        return "WB"

    if has_supplier and has_quantity:
        return "LOCAL"

    return None


def dataframe_from_bytes(data: bytes, filename: str | None) -> pd.DataFrame:
    suffix = Path(filename or "").suffix.lower()

    if suffix == ".csv":
        return _read_csv(data)

    try:
        return pd.read_excel(BytesIO(data))
    except Exception:  # pragma: no cover - fallback path
        try:
            return _read_csv(data)
        except Exception as csv_exc:  # pragma: no cover - propagate details
            raise LocalFileError("Не удалось прочитать файл как Excel или CSV") from csv_exc


def _read_csv(data: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(data), sep=None, engine="python")
    except Exception:
        return pd.read_csv(BytesIO(data), sep=";")


def prepare_wb_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = rename_known_columns(df.copy())
    required = {"supplierArticle", "nmId", "warehouseName", "quantity"}
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise LocalFileError(
            "Не узнаю формат WB. Нужны столбцы supplierArticle/nmId/warehouseName/quantity"
        )

    normalized["supplierArticle"] = (
        normalized["supplierArticle"].astype(str).str.strip().str.upper()
    )
    normalized = normalized[normalized["supplierArticle"] != ""]
    normalized["nmId"] = pd.to_numeric(normalized["nmId"], errors="coerce")
    normalized = normalized.dropna(subset=["nmId"])
    normalized["nmId"] = normalized["nmId"].astype(int)

    base = (
        normalized[["supplierArticle", "nmId"]]
        .drop_duplicates(subset=["supplierArticle", "nmId"])
        .reset_index(drop=True)
    )
    base = base.rename(columns={"supplierArticle": "Артикул_norm"})
    return base


def prepare_local_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = rename_known_columns(df.copy())
    required = {"supplierArticle", "quantity"}
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise LocalFileError("Не узнаю формат. Нужны столбцы Артикул/Количество")

    normalized["supplierArticle"] = normalized["supplierArticle"].astype(str).str.strip()
    normalized = normalized[normalized["supplierArticle"] != ""]
    normalized["quantity"] = pd.to_numeric(normalized["quantity"], errors="coerce").fillna(0)

    normalized["Артикул_norm"] = normalized["supplierArticle"].str.upper()

    grouped = (
        normalized.groupby("Артикул_norm", as_index=False)
        .agg(
            {
                "supplierArticle": "first",
                "quantity": "sum",
            }
        )
        .rename(columns={"supplierArticle": "Артикул", "quantity": "Количество"})
    )
    grouped["Количество"] = grouped["Количество"].round().astype(int)
    grouped["Артикул"] = grouped["Артикул"].astype(str).str.strip().str.upper()
    return grouped


def perform_join(
    wb_df: pd.DataFrame, local_df: pd.DataFrame
) -> tuple[pd.DataFrame, LocalJoinStats]:
    wb_base = prepare_wb_dataframe(wb_df)
    local_base = prepare_local_dataframe(local_df)

    wb_base = wb_base.rename(columns={"Артикул_norm": "Артикул_norm"})
    wb_base["Артикул_norm"] = wb_base["Артикул_norm"].astype(str)

    local_base["Артикул_norm"] = local_base["Артикул_norm"].astype(str)

    merged = wb_base.merge(local_base, left_on="Артикул_norm", right_on="Артикул_norm", how="inner")

    wb_count = len(wb_base)
    matched = len(merged)
    dropped = max(len(local_base) - matched, 0)

    result = (
        merged.rename(columns={"Артикул": "Артикул", "Количество": "Количество_склад"})[
            ["Артикул", "nmId", "Количество_склад"]
        ]
        .sort_values("Артикул")
        .reset_index(drop=True)
    )

    stats = LocalJoinStats(wb_count=wb_count, matched=matched, dropped=dropped)
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
    payload = dataframe_to_xlsx_bytes(df)

    latest_path = directory / "result.xlsx"
    latest_path.write_bytes(payload)
    (directory / f"result_{timestamp}.xlsx").write_bytes(payload)
    return latest_path


def load_latest(chat_id: int, kind: str) -> pd.DataFrame | None:
    directory = ensure_local_dir(chat_id)
    path = directory / f"{kind}.xlsx"
    if not path.exists():
        return None
    return pd.read_excel(path)


def build_local_preview(df: pd.DataFrame, *, limit: int = 25) -> tuple[list[str], int]:
    total = len(df)
    subset = df.head(limit)
    lines = [f"• {row['Артикул']} — {row['Количество_склад']}" for _, row in subset.iterrows()]
    return lines, total


def recompute_local_result(chat_id: int) -> tuple[pd.DataFrame, LocalJoinStats] | None:
    wb_df = load_latest(chat_id, "wb")
    local_df = load_latest(chat_id, "local")
    if wb_df is None or local_df is None:
        return None

    result_df, stats = perform_join(wb_df, local_df)
    save_result(chat_id, result_df)
    return result_df, stats


def build_local_only_dataframe(chat_id: int) -> pd.DataFrame | None:
    local_df = load_latest(chat_id, "local")
    if local_df is None:
        return None
    aggregated = prepare_local_dataframe(local_df)
    return aggregated[["Артикул", "Количество"]]

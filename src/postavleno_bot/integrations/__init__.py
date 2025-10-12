"""External integrations used by the bot."""

from .moysklad import fetch_ms_stocks_all
from .wildberries import WBStockItem, fetch_wb_stocks_all

__all__ = [
    "WBStockItem",
    "fetch_wb_stocks_all",
    "fetch_ms_stocks_all",
]

"""External integrations used by the bot."""

from .wildberries import WBStockItem, fetch_wb_stocks_all

__all__ = [
    "WBStockItem",
    "fetch_wb_stocks_all",
]

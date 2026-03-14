from __future__ import annotations

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger("stockpicker.sources.edgar")


class EdgarSource:
    """SEC EDGAR data source stub. TODO: implement with SEC EDGAR API."""

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.warning("EDGAR source not yet implemented — returning empty")
        return pd.DataFrame(columns=[
            "quarter", "eps", "pe_ratio", "revenue", "gross_margin",
            "operating_margin", "roe", "debt_to_equity", "free_cash_flow",
        ])

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None

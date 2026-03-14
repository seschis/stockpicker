from __future__ import annotations

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger("stockpicker.sources.fred")


class FredSource:
    """FRED data source stub. TODO: implement with fredapi or direct API calls."""

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.warning("FRED source not yet implemented — returning empty")
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None

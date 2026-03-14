from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


class DataSource(Protocol):
    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """Returns DataFrame with columns: date, open, high, low, close, volume"""
        ...

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        """Returns DataFrame with columns: quarter, eps, pe_ratio, revenue,
        gross_margin, operating_margin, roe, debt_to_equity, free_cash_flow"""
        ...

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        """Returns DataFrame with columns: date, headline, source, sentiment_score.
        Returns None if the source does not support news."""
        ...

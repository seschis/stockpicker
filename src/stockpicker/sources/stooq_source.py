from __future__ import annotations

import io
import logging
import urllib.request
from datetime import date

import pandas as pd

logger = logging.getLogger("stockpicker.sources.stooq")


class StooqSource:
    """Free stock price data from Stooq.com — no API key required."""

    BASE_URL = "https://stooq.com/q/d/l/"

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.info("Fetching prices for %s from %s to %s via Stooq", ticker, start, end)
        symbol = f"{ticker.lower()}.us"
        d1 = start.strftime("%Y%m%d")
        d2 = end.strftime("%Y%m%d")
        url = f"{self.BASE_URL}?s={symbol}&d1={d1}&d2={d2}&i=d"

        try:
            response = urllib.request.urlopen(url, timeout=15)
            data = response.read().decode()
        except Exception as e:
            logger.error("Failed to fetch from Stooq: %s", e)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = pd.read_csv(io.StringIO(data))
        if df.empty or "Date" not in df.columns:
            logger.warning("No price data returned for %s from Stooq", ticker)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = df.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        df = df.sort_values("date").reset_index(drop=True)
        return pd.DataFrame(df[["date", "open", "high", "low", "close", "volume"]])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        # Stooq doesn't provide fundamentals
        return pd.DataFrame(columns=[
            "quarter", "eps", "pe_ratio", "revenue", "gross_margin",
            "operating_margin", "roe", "debt_to_equity", "free_cash_flow",
        ])

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None

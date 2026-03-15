from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import yfinance as yf

logger = logging.getLogger("stockpicker.sources.yfinance")


class YFinanceSource:
    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.info("Fetching prices for %s from %s to %s", ticker, start, end)
        t = yf.Ticker(ticker)
        hist = t.history(start=str(start), end=str(end), auto_adjust=False)
        if hist.empty:
            logger.warning("No price data returned for %s", ticker)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df["date"] = pd.DatetimeIndex(df.index).strftime("%Y-%m-%d")
        df = df.reset_index(drop=True)
        return pd.DataFrame(df[["date", "open", "high", "low", "close", "volume"]])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.info("Fetching fundamentals for %s", ticker)
        t = yf.Ticker(ticker)
        info = t.info
        quarterly = t.quarterly_financials

        if quarterly.empty:
            logger.warning("No fundamental data for %s", ticker)
            return pd.DataFrame(columns=[
                "quarter", "eps", "pe_ratio", "revenue", "gross_margin",
                "operating_margin", "roe", "debt_to_equity", "free_cash_flow",
            ])

        records = []
        for col in quarterly.columns:
            quarter_str = f"{col.year}-Q{(col.month - 1) // 3 + 1}" if hasattr(col, "year") else str(col)
            revenue = quarterly.loc["Total Revenue", col] if "Total Revenue" in quarterly.index else None
            records.append({
                "quarter": quarter_str,
                "eps": info.get("trailingEps"),
                "pe_ratio": info.get("trailingPE"),
                "revenue": revenue,
                "gross_margin": info.get("grossMargins"),
                "operating_margin": info.get("operatingMargins"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"),
            })
        return pd.DataFrame(records)

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None

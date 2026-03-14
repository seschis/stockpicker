from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.metrics_computer")


class MetricsComputer:
    def __init__(self, store: Store) -> None:
        self.store = store

    def compute_all(self, tickers: list[str]) -> None:
        for ticker in tickers:
            try:
                self._compute_ticker_info(ticker)
                self._compute_derived_metrics(ticker)
            except Exception as e:
                logger.error("Failed to compute metrics for %s: %s", ticker, e)

    def _compute_ticker_info(self, ticker: str) -> None:
        prices = self.store.get_prices(ticker)
        if prices.empty:
            return
        fund = self.store.get_fundamentals(ticker)

        last_price = float(prices.iloc[-1]["close"])
        avg_volume = float(prices["volume"].tail(30).mean())

        # Estimate market cap from PE and EPS if available
        market_cap = None
        if not fund.empty:
            pe = fund.iloc[-1].get("pe_ratio")
            eps = fund.iloc[-1].get("eps")
            if pe and eps and pe > 0 and eps > 0:
                market_cap = last_price / eps * eps * pe * 1e6  # rough estimate

        # Get sector/country from fundamentals or default
        sector = "Unknown"
        country = "US"

        self.store._conn.execute(
            "INSERT OR REPLACE INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, market_cap, sector, country, avg_volume, last_price),
        )
        self.store._conn.commit()

    def _compute_derived_metrics(self, ticker: str) -> None:
        prices = self.store.get_prices(ticker)
        if len(prices) < 2:
            return

        closes = prices["close"].values.astype(float)

        # 90-day price return (or max available)
        lookback = min(90, len(closes))
        price_return_90d = (closes[-1] - closes[-lookback]) / closes[-lookback]

        # Revenue growth YoY (placeholder — needs multiple quarters)
        fund = self.store.get_fundamentals(ticker)
        revenue_growth_yoy = None
        if len(fund) >= 2:
            rev_recent = fund.iloc[-1].get("revenue")
            rev_prior = fund.iloc[-2].get("revenue")
            if rev_recent and rev_prior and rev_prior > 0:
                revenue_growth_yoy = (rev_recent - rev_prior) / rev_prior

        self.store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
            "VALUES (?, ?, ?, ?)",
            (ticker, price_return_90d, revenue_growth_yoy, None),
        )
        self.store._conn.commit()

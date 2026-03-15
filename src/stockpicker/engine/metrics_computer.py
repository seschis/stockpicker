from __future__ import annotations

import logging

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

        last_price = float(prices.iloc[-1]["close"])  # pyright: ignore[reportArgumentType]
        avg_volume = float(prices["volume"].tail(30).mean())  # pyright: ignore[reportArgumentType]

        # Preserve existing market_cap, sector, country if already set
        existing = self.store.get_ticker_info()
        row = existing[existing["ticker"] == ticker]
        if not row.empty:
            market_cap = row.iloc[0]["market_cap"] if row.iloc[0]["market_cap"] is not None else None
            sector = row.iloc[0]["sector"] if row.iloc[0]["sector"] not in (None, "Unknown") else "Unknown"
            country = row.iloc[0]["country"] if row.iloc[0]["country"] is not None else "US"
        else:
            market_cap = None
            sector = "Unknown"
            country = "US"

        self.store.upsert_ticker_info(ticker, market_cap, sector, country, avg_volume, last_price)

    def _compute_derived_metrics(self, ticker: str) -> None:
        prices = self.store.get_prices(ticker)
        if len(prices) < 2:
            return

        closes = prices["close"].values.astype(float)

        # 90-day price return (or max available)
        lookback = min(90, len(closes))
        price_return_90d = (closes[-1] - closes[-lookback]) / closes[-lookback] if closes[-lookback] != 0 else 0.0

        # Revenue growth YoY (placeholder — needs multiple quarters)
        fund = self.store.get_fundamentals(ticker)
        revenue_growth_yoy = None
        if len(fund) >= 2:
            rev_recent = fund.iloc[-1].get("revenue")
            rev_prior = fund.iloc[-2].get("revenue")
            if rev_recent and rev_prior and rev_prior > 0:
                revenue_growth_yoy = (rev_recent - rev_prior) / rev_prior

        self.store.upsert_computed_metrics(ticker, price_return_90d, revenue_growth_yoy, None)

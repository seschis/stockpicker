from __future__ import annotations

import logging
from datetime import date
from typing import Any

from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.ingester")


class Ingester:
    def __init__(self, store: Store, sources: dict[str, Any]) -> None:
        self.store = store
        self.sources = sources

    def ingest(self, tickers: list[str], start: date, end: date) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for ticker in tickers:
            results[ticker] = self._ingest_ticker(ticker, start, end)
        return results

    def _ingest_ticker(self, ticker: str, start: date, end: date) -> dict:
        result: dict[str, Any] = {"prices": 0, "fundamentals": 0}
        for source_name, source in self.sources.items():
            try:
                prices_df = source.fetch_prices(ticker, start, end)
                if prices_df is not None and not prices_df.empty:
                    self.store.upsert_prices(ticker, prices_df, source=source_name)
                    result["prices"] += len(prices_df)
                    logger.info("Ingested %d price rows for %s from %s", len(prices_df), ticker, source_name)
            except Exception as e:
                logger.error("Failed to fetch prices for %s from %s: %s", ticker, source_name, e)
                result["error"] = str(e)

            try:
                fund_df = source.fetch_fundamentals(ticker)
                if fund_df is not None and not fund_df.empty:
                    self.store.upsert_fundamentals(ticker, fund_df, source=source_name)
                    result["fundamentals"] += len(fund_df)
            except Exception as e:
                logger.error("Failed to fetch fundamentals for %s from %s: %s", ticker, source_name, e)

            try:
                news_df = source.fetch_news(ticker, start, end)
                if news_df is not None and not news_df.empty:
                    logger.info("Ingested %d news rows for %s", len(news_df), ticker)
            except Exception as e:
                logger.error("Failed to fetch news for %s from %s: %s", ticker, source_name, e)

        return result

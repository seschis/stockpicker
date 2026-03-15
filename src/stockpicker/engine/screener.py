from __future__ import annotations

import logging

import pandas as pd

from stockpicker.config.models import ScreenConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.screener")

RANGE_FILTERS = {"market_cap", "avg_volume", "last_price", "pe_ratio"}
LIST_FILTERS = {"sector", "country"}
MIN_FILTERS = {"avg_volume_min": "avg_volume", "price_min": "last_price"}


class Screener:
    def __init__(self, store: Store) -> None:
        self.store = store

    def screen(self, config: ScreenConfig) -> pd.DataFrame:
        logger.info("Running screen: %s", config.name)
        df = self.store.get_ticker_info()
        if df.empty:
            logger.warning("No ticker info in database")
            return df

        for key, value in config.filters.items():
            if key in RANGE_FILTERS and isinstance(value, list) and len(value) == 2:
                low, high = value
                df = df[df[key].between(low, high)]  # pyright: ignore[reportAttributeAccessIssue]
            elif key in LIST_FILTERS and isinstance(value, list):
                df = df[df[key].isin(value)]  # pyright: ignore[reportAttributeAccessIssue]
            elif key in MIN_FILTERS:
                col = MIN_FILTERS[key]
                df = df[df[col] >= value]
            else:
                logger.warning("Unknown filter: %s", key)

        logger.info("Screen '%s' returned %d tickers", config.name, len(df))
        result: pd.DataFrame = df.reset_index(drop=True)  # pyright: ignore[reportAttributeAccessIssue, reportAssignmentType]
        return result

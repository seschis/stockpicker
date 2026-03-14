from pathlib import Path

import pandas as pd

from stockpicker.config.models import ScreenConfig
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener


def _seed_db(store: Store) -> None:
    """Seed DB with test tickers having fundamentals."""
    for ticker, pe, mcap, sector, country, vol, price in [
        ("AAPL", 28.0, 3_000_000_000_000, "Technology", "US", 80_000_000, 180.0),
        ("MSFT", 35.0, 2_800_000_000_000, "Technology", "US", 30_000_000, 400.0),
        ("SMALL", 15.0, 500_000_000, "Technology", "US", 200_000, 12.0),
        ("BIGFIN", 12.0, 5_000_000_000, "Financials", "US", 5_000_000, 50.0),
        ("MIDTECH", 20.0, 5_000_000_000, "Technology", "US", 1_000_000, 75.0),
    ]:
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, quarter, pe_ratio) VALUES (?, ?, ?)",
            (ticker, "2024-Q1", pe),
        )
        # Store metadata as a simple ticker_info table
        store._conn.execute(
            "CREATE TABLE IF NOT EXISTS ticker_info "
            "(ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, country TEXT, avg_volume REAL, last_price REAL)"
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, mcap, sector, country, vol, price),
        )
    store._conn.commit()


def test_screener_filters_by_market_cap(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_db(store)
    config = ScreenConfig(
        name="Mid Cap",
        filters={"market_cap": [2_000_000_000, 10_000_000_000]},
    )
    screener = Screener(store)
    result = screener.screen(config)
    tickers = result["ticker"].tolist()
    assert "MIDTECH" in tickers
    assert "BIGFIN" in tickers
    assert "AAPL" not in tickers  # too large
    assert "SMALL" not in tickers  # too small


def test_screener_filters_by_sector(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_db(store)
    config = ScreenConfig(
        name="Tech Only",
        filters={"sector": ["Technology"]},
    )
    screener = Screener(store)
    result = screener.screen(config)
    tickers = result["ticker"].tolist()
    assert "BIGFIN" not in tickers
    assert "AAPL" in tickers

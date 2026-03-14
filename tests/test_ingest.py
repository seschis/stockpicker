from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from stockpicker.db.store import Store
from stockpicker.engine.ingester import Ingester


def test_ingester_incremental_fetches_from_last_date(tmp_path: Path):
    store = Store(tmp_path / "test.db")

    # Pre-seed with data up to Jan 15
    existing = pd.DataFrame({
        "date": ["2024-01-10", "2024-01-11", "2024-01-12", "2024-01-15"],
        "open": [100.0] * 4, "high": [101.0] * 4,
        "low": [99.0] * 4, "close": [100.5] * 4, "volume": [1000000] * 4,
    })
    store.upsert_prices("AAPL", existing, source="test")

    # Mock source that records what date range was requested
    mock_source = MagicMock()
    mock_source.fetch_prices.return_value = pd.DataFrame({
        "date": ["2024-01-16"], "open": [101.0], "high": [102.0],
        "low": [100.0], "close": [101.5], "volume": [1100000],
    })
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    # Verify fetch_prices was called with start=Jan 16 (day after last ingested)
    call_args = mock_source.fetch_prices.call_args
    assert call_args[0][1] == date(2024, 1, 16)  # start should be day after last


def test_ingester_ingests_prices(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    mock_source = MagicMock()
    mock_source.fetch_prices.return_value = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03"],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    result = ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert result["AAPL"]["prices"] == 2
    prices = store.get_prices("AAPL")
    assert len(prices) == 2


def test_ingester_continues_on_source_failure(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    mock_source = MagicMock()
    mock_source.fetch_prices.side_effect = Exception("API down")
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    result = ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert result["AAPL"]["prices"] == 0
    assert "error" in result["AAPL"]

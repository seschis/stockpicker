from pathlib import Path

import numpy as np
import pandas as pd

from stockpicker.db.store import Store
from stockpicker.engine.metrics_computer import MetricsComputer


def _seed_raw_data(store: Store) -> None:
    dates = pd.bdate_range("2024-01-02", periods=90)
    for ticker, base, drift in [("AAPL", 150.0, 0.002), ("MSFT", 350.0, -0.001)]:
        np.random.seed(hash(ticker) % 2**31)
        prices = base * (1 + np.random.normal(drift, 0.015, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": [1000000 + i * 1000 for i in range(len(dates))],
        })
        store.upsert_prices(ticker, df, source="test")
        store.upsert_fundamentals(ticker, pd.DataFrame({
            "quarter": ["2024-Q1"],
            "eps": [5.0], "pe_ratio": [28.0], "revenue": [1e10],
            "gross_margin": [0.4], "operating_margin": [0.3], "roe": [0.25],
            "debt_to_equity": [1.5], "free_cash_flow": [5e9],
        }), source="test")


def test_compute_ticker_info(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_raw_data(store)
    computer = MetricsComputer(store)
    computer.compute_all(["AAPL", "MSFT"])

    df = store.get_ticker_info()
    assert len(df) == 2
    assert all(col in df.columns for col in ["ticker", "market_cap", "avg_volume", "last_price"])


def test_compute_metrics(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_raw_data(store)
    computer = MetricsComputer(store)
    computer.compute_all(["AAPL", "MSFT"])

    df = pd.read_sql_query("SELECT * FROM computed_metrics", store._conn)
    assert len(df) == 2
    assert "price_return_90d" in df.columns


def test_compute_metrics_zero_price(tmp_path: Path):
    """Price data starting at 0 should not crash."""
    store = Store(tmp_path / "test.db")
    dates = pd.bdate_range("2024-01-02", periods=10)
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "open": [0.0] + [1.0] * 9,
        "high": [0.0] + [1.0] * 9,
        "low": [0.0] + [1.0] * 9,
        "close": [0.0] + [1.0] * 9,
        "volume": [1000000] * 10,
    })
    store.upsert_prices("ZERO", df, source="test")
    store.upsert_fundamentals("ZERO", pd.DataFrame({
        "quarter": ["2024-Q1"], "eps": [1.0], "pe_ratio": [10.0], "revenue": [1e6],
    }), source="test")
    computer = MetricsComputer(store)
    computer.compute_all(["ZERO"])  # should not raise
    result = pd.read_sql_query("SELECT * FROM computed_metrics WHERE ticker = 'ZERO'", store._conn)
    assert len(result) == 1
    assert result.iloc[0]["price_return_90d"] == 0.0

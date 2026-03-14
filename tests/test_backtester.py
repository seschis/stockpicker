from pathlib import Path

import pandas as pd
import numpy as np

from stockpicker.config.models import (
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.backtester import Backtester


def _seed_backtest_db(store: Store) -> None:
    """Create 60 days of price data for 3 tickers."""
    dates = pd.bdate_range("2024-01-02", periods=60)
    for ticker, base_price in [("AAA", 100.0), ("BBB", 50.0), ("CCC", 200.0)]:
        np.random.seed(hash(ticker) % 2**31)
        prices = base_price * (1 + np.random.normal(0.001, 0.02, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": [1000000] * len(dates),
        })
        store.upsert_prices(ticker, df, source="test")


def test_backtester_runs_and_returns_metrics(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_backtest_db(store)

    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=10, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(name="test-strat", screen="test", model="test", rules=rules)

    backtester = Backtester(store)
    # Provide pre-scored rankings per date
    rankings = {}
    dates = pd.bdate_range("2024-01-02", periods=60)
    for d in dates:
        rankings[d.strftime("%Y-%m-%d")] = ["AAA", "BBB", "CCC"]

    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-03-25")

    assert "total_return" in result.metrics
    assert "sharpe_ratio" in result.metrics
    assert "max_drawdown" in result.metrics
    assert len(result.trades) > 0


def test_backtester_applies_stop_loss(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    # Create a ticker that drops 15% immediately
    dates = pd.bdate_range("2024-01-02", periods=20)
    prices = [100.0] + [84.0] * 19  # 16% drop
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "open": prices, "high": prices, "low": prices, "close": prices,
        "volume": [1000000] * len(dates),
    })
    store.upsert_prices("DROP", df, source="test")

    rules = StrategyRules(
        buy=BuyRules(top_n=1, position_size="equal"),
        sell=SellRules(hold_days=30, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=1, max_position_pct=1.0),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(name="test-stop", screen="test", model="test", rules=rules)
    rankings = {d.strftime("%Y-%m-%d"): ["DROP"] for d in dates}

    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-01-31")

    sell_trades = [t for t in result.trades if t["action"] == "SELL"]
    assert len(sell_trades) >= 1  # stop loss should trigger

from pathlib import Path

import numpy as np
import pandas as pd

from stockpicker.config.models import (
    BuyRules,
    CostRules,
    PortfolioRules,
    SellRules,
    StrategyConfig,
    StrategyRules,
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


def test_backtest_includes_benchmark_metrics(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_backtest_db(store)

    # Seed benchmark prices
    dates = pd.bdate_range("2024-01-02", periods=60)
    bench_closes = np.linspace(100.0, 120.0, len(dates))
    bench_df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "open": bench_closes * 0.99,
        "high": bench_closes * 1.01,
        "low": bench_closes * 0.98,
        "close": bench_closes,
        "volume": [1000000] * len(dates),
    })
    store.upsert_prices("BENCH", bench_df, source="test")

    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=10, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(
        name="test-bench", screen="test", model="test", rules=rules,
        benchmarks=["BENCH"],
    )

    backtester = Backtester(store)
    rankings = {d.strftime("%Y-%m-%d"): ["AAA", "BBB", "CCC"] for d in dates}
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-03-25")

    assert "BENCH" in result.benchmark_metrics
    bench = result.benchmark_metrics["BENCH"]
    assert abs(bench["total_return"] - 0.20) < 0.01
    assert bench["trading_days"] > 0


def test_backtester_delisted_stock_exits_at_last_known_price(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    # Ticker has prices for days 1-5 only, then nothing for days 6-10
    dates_with_prices = pd.bdate_range("2024-01-02", periods=5)
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates_with_prices],
        "open": [100.0] * 5,
        "high": [101.0] * 5,
        "low": [99.0] * 5,
        "close": [100.0, 101.0, 102.0, 103.0, 104.0],
        "volume": [1000000] * 5,
    })
    store.upsert_prices("DELIST", df, source="test")

    rules = StrategyRules(
        buy=BuyRules(top_n=1, position_size="equal"),
        sell=SellRules(hold_days=30, stop_loss=-0.50),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=1, max_position_pct=1.0),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(name="test-delist", screen="test", model="test", rules=rules)

    all_dates = pd.bdate_range("2024-01-02", periods=10)
    rankings = {d.strftime("%Y-%m-%d"): ["DELIST"] for d in all_dates}

    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-01-15")

    sell_trades = [t for t in result.trades if t["action"] == "SELL"]
    assert len(sell_trades) >= 1
    # Should exit at last known close (104.0), not at entry price
    assert sell_trades[0]["price"] == 104.0

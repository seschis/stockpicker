import numpy as np
import pandas as pd

from stockpicker.engine.reporter import Reporter


def test_reporter_strategy_report():
    equity_data = {
        "date": pd.bdate_range("2024-01-02", periods=60).strftime("%Y-%m-%d").tolist(),
        "equity": (100000 * (1 + np.random.normal(0.001, 0.01, 60)).cumprod()).tolist(),
    }
    equity_df = pd.DataFrame(equity_data)
    trades = [
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-02", "price": 150.0, "shares": 100},
        {"ticker": "AAPL", "action": "SELL", "date": "2024-02-01", "price": 160.0, "shares": 100},
    ]

    reporter = Reporter()
    report = reporter.strategy_report(
        name="test", equity_curve=equity_df, trades=trades, initial_capital=100000
    )
    assert "total_return" in report
    assert "sharpe_ratio" in report
    assert "max_drawdown" in report
    assert "win_rate" in report
    assert "total_trades" in report


def test_reporter_fifo_win_rate_multiple_cycles():
    """3 buy/sell cycles for same ticker: 2 wins, 1 loss."""
    equity_data = {
        "date": pd.bdate_range("2024-01-02", periods=30).strftime("%Y-%m-%d").tolist(),
        "equity": (100000 * (1 + np.random.normal(0.001, 0.01, 30)).cumprod()).tolist(),
    }
    equity_df = pd.DataFrame(equity_data)
    trades = [
        # Cycle 1: win (buy 100, sell 110)
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-02", "price": 100.0, "shares": 10},
        {"ticker": "AAPL", "action": "SELL", "date": "2024-01-10", "price": 110.0, "shares": 10},
        # Cycle 2: loss (buy 120, sell 105)
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-11", "price": 120.0, "shares": 10},
        {"ticker": "AAPL", "action": "SELL", "date": "2024-01-18", "price": 105.0, "shares": 10},
        # Cycle 3: win (buy 100, sell 130)
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-19", "price": 100.0, "shares": 10},
        {"ticker": "AAPL", "action": "SELL", "date": "2024-01-25", "price": 130.0, "shares": 10},
    ]
    reporter = Reporter()
    report = reporter.strategy_report("test", equity_df, trades, 100000)
    assert abs(report["win_rate"] - 0.6667) < 0.01


def test_reporter_single_day_equity():
    """Single data point equity curve should not crash."""
    equity_df = pd.DataFrame({"date": ["2024-01-02"], "equity": [100000.0]})
    trades = [
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-02", "price": 150.0, "shares": 100},
    ]
    reporter = Reporter()
    report = reporter.strategy_report("test", equity_df, trades, 100000)
    assert report["total_return"] == 0.0
    assert report["sharpe_ratio"] == 0.0
    assert report["max_drawdown"] == 0.0


def test_reporter_compare():
    reporter = Reporter()
    reports = {
        "strat_a": {"total_return": 0.15, "sharpe_ratio": 1.2, "max_drawdown": -0.08},
        "strat_b": {"total_return": 0.10, "sharpe_ratio": 0.9, "max_drawdown": -0.12},
    }
    comparison = reporter.compare(reports)
    assert len(comparison) == 2
    assert "strategy" in comparison.columns


def test_benchmark_report_buy_and_hold():
    """Price goes from 100 to 120 = 20% gain."""
    dates = pd.bdate_range("2024-01-02", periods=60).strftime("%Y-%m-%d").tolist()
    # Linear from 100 to 120
    closes = np.linspace(100.0, 120.0, 60)
    prices = pd.DataFrame({"date": dates, "close": closes})

    reporter = Reporter()
    report = reporter.benchmark_report("VOO", prices, initial_capital=100000)

    assert report["strategy"] == "VOO (benchmark)"
    assert abs(report["total_return"] - 0.20) < 0.01
    assert report["sharpe_ratio"] > 0
    assert report["max_drawdown"] == 0.0  # monotonically increasing


def test_benchmark_report_with_drawdown():
    """Price dips mid-period — verify max_drawdown is negative."""
    closes = [100.0, 105.0, 110.0, 95.0, 90.0, 100.0, 110.0, 115.0, 120.0, 125.0]
    dates = pd.bdate_range("2024-01-02", periods=len(closes)).strftime("%Y-%m-%d").tolist()
    prices = pd.DataFrame({"date": dates, "close": closes})

    reporter = Reporter()
    report = reporter.benchmark_report("SPY", prices, initial_capital=100000)

    assert report["max_drawdown"] < 0
    # Max drawdown should be from 110 peak to 90 trough = -18.18%
    assert abs(report["max_drawdown"] - ((90.0 - 110.0) / 110.0)) < 0.01


def test_format_report_benchmark():
    """format_report handles missing win_rate/total_trades gracefully."""
    reporter = Reporter()
    bench_report = {
        "strategy": "VOO (benchmark)",
        "total_return": 0.12,
        "annualized_return": 0.25,
        "sharpe_ratio": 1.5,
        "sortino_ratio": 2.0,
        "max_drawdown": -0.05,
        "trading_days": 120,
    }
    formatted = reporter.format_report(bench_report)
    assert "VOO (benchmark)" in formatted
    assert "Win Rate" not in formatted
    assert "Total Trades" not in formatted
    assert "Trading Days" in formatted

import pandas as pd
import numpy as np

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


def test_reporter_compare():
    reporter = Reporter()
    reports = {
        "strat_a": {"total_return": 0.15, "sharpe_ratio": 1.2, "max_drawdown": -0.08},
        "strat_b": {"total_return": 0.10, "sharpe_ratio": 0.9, "max_drawdown": -0.12},
    }
    comparison = reporter.compare(reports)
    assert len(comparison) == 2
    assert "strategy" in comparison.columns

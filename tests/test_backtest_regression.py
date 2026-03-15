"""Golden-file regression test for the backtester.

On first run, this generates the expected output file.
On subsequent runs, it verifies the backtester produces identical results.
"""
import json
from pathlib import Path

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

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PRICES = FIXTURES / "golden_backtest_prices.csv"
GOLDEN_EXPECTED = FIXTURES / "golden_backtest_expected.json"


def _setup_golden_db(tmp_path: Path) -> Store:
    store = Store(tmp_path / "golden.db")
    prices_df = pd.read_csv(GOLDEN_PRICES)
    for ticker in prices_df["ticker"].unique():
        ticker_df = prices_df[prices_df["ticker"] == ticker].drop(columns=["ticker"])
        store.upsert_prices(ticker, ticker_df, source="golden")
    return store


def _run_golden_backtest(store: Store):
    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=5, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=10000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(commission_per_trade=1.0, slippage_bps=10),
    )
    config = StrategyConfig(name="golden-test", screen="test", model="test", rules=rules)
    rankings = {
        "2024-01-02": ["GOLD1", "GOLD2"],
        "2024-01-03": ["GOLD1", "GOLD2"],
        "2024-01-04": ["GOLD1", "GOLD2"],
        "2024-01-05": ["GOLD1", "GOLD2"],
        "2024-01-08": ["GOLD1", "GOLD2"],
        "2024-01-09": ["GOLD1", "GOLD2"],
        "2024-01-10": ["GOLD1", "GOLD2"],
        "2024-01-11": ["GOLD1", "GOLD2"],
        "2024-01-12": ["GOLD1", "GOLD2"],
        "2024-01-15": ["GOLD1", "GOLD2"],
    }
    backtester = Backtester(store)
    return backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-01-15")


def test_backtest_golden_file(tmp_path: Path):
    store = _setup_golden_db(tmp_path)
    result = _run_golden_backtest(store)

    actual = {
        "metrics": result.metrics,
        "equity_curve": result.equity_curve["equity"].round(2).tolist(),
        "trade_count": len(result.trades),
    }

    if not GOLDEN_EXPECTED.exists():
        # First run: generate the golden file
        GOLDEN_EXPECTED.write_text(json.dumps(actual, indent=2))
        print(f"Golden file generated at {GOLDEN_EXPECTED}")
        print(f"Metrics: {actual['metrics']}")
        print("Review and commit this file to lock in the expected output.")
        return

    # Subsequent runs: compare against golden file
    expected = json.loads(GOLDEN_EXPECTED.read_text())

    assert actual["trade_count"] == expected["trade_count"], (
        f"Trade count mismatch: {actual['trade_count']} != {expected['trade_count']}"
    )

    assert actual["equity_curve"] == expected["equity_curve"], (
        f"Equity curve mismatch.\n"
        f"Actual:   {actual['equity_curve']}\n"
        f"Expected: {expected['equity_curve']}"
    )

    for key in expected["metrics"]:
        assert abs(actual["metrics"][key] - expected["metrics"][key]) < 1e-4, (
            f"Metric '{key}' mismatch: {actual['metrics'][key]} != {expected['metrics'][key]}"
        )

    store.close()

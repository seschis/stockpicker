"""End-to-end test: ingest → screen → score → backtest pipeline using fixture data."""
from pathlib import Path

import pandas as pd
import numpy as np

from stockpicker.config.models import (
    ScreenConfig, ModelConfig, FactorConfig,
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.backtester import Backtester


def test_full_pipeline(tmp_path: Path):
    store = Store(tmp_path / "test.db")

    # Seed price data for 5 tickers
    dates = pd.bdate_range("2024-01-02", periods=60)
    tickers_data = {
        "ALPHA": (100.0, 0.002),
        "BETA": (50.0, -0.001),
        "GAMMA": (200.0, 0.003),
        "DELTA": (75.0, 0.0),
        "EPSILON": (150.0, 0.001),
    }

    for ticker, (base, drift) in tickers_data.items():
        np.random.seed(hash(ticker) % 2**31)
        prices = base * (1 + np.random.normal(drift, 0.015, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": [1000000] * len(dates),
        })
        store.upsert_prices(ticker, df, source="test")

        ret_90d = (prices[-1] - prices[0]) / prices[0]
        store._conn.execute(
            "INSERT INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, 5_000_000_000, "Technology", "US", 1_000_000, float(prices[-1])),
        )
        store._conn.execute(
            "INSERT INTO fundamentals (ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", 20.0 + np.random.uniform(-5, 10), np.random.uniform(0.1, 0.3)),
        )
        store._conn.execute(
            "INSERT INTO computed_metrics (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
            "VALUES (?, ?, ?, ?)",
            (ticker, float(ret_90d), 0.15, 0.5),
        )
    store._conn.commit()

    # Screen
    screen_config = ScreenConfig(name="All Tech", filters={"sector": ["Technology"]})
    screener = Screener(store)
    screened = screener.screen(screen_config)
    assert len(screened) == 5

    # Score
    model = ModelConfig(name="test-model", factors=[
        FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
        FactorConfig(name="momentum", metric="price_return_90d", weight=0.5, direction="higher_is_better"),
    ])
    scorer = Scorer(store)
    scored = scorer.score(tickers=screened["ticker"].tolist(), model=model)
    assert len(scored) == 5

    # Backtest
    rules = StrategyRules(
        buy=BuyRules(top_n=3, position_size="equal"),
        sell=SellRules(hold_days=20, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=3, max_position_pct=0.4),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=5),
    )
    config = StrategyConfig(name="integration-test", screen="test", model="test-model", rules=rules)
    ranked = scored["ticker"].tolist()
    rankings = {d.strftime("%Y-%m-%d"): ranked for d in dates}

    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-03-25")

    assert result.metrics["trading_days"] > 0
    assert len(result.trades) > 0
    assert "total_return" in result.metrics
    assert "sharpe_ratio" in result.metrics

    store.close()

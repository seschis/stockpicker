from pathlib import Path
import numpy as np
import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer


def _seed_scoring_db(store: Store) -> None:
    for ticker, pe, roe, ret_90d in [
        ("AAPL", 28.0, 0.40, 0.15),
        ("MSFT", 35.0, 0.35, 0.10),
        ("GOOG", 22.0, 0.25, 0.20),
        ("META", 18.0, 0.20, 0.25),
    ]:
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", pe, roe),
        )
        # Add price return data
        store._conn.execute(
            "CREATE TABLE IF NOT EXISTS computed_metrics "
            "(ticker TEXT PRIMARY KEY, price_return_90d REAL, revenue_growth_yoy REAL, news_sentiment_30d REAL)"
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) VALUES (?, ?, ?, ?)",
            (ticker, ret_90d, 0.15, 0.5),
        )
    store._conn.commit()


def test_scorer_produces_ranked_output(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_scoring_db(store)
    model = ModelConfig(
        name="test-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
            FactorConfig(name="momentum", metric="price_return_90d", weight=0.5, direction="higher_is_better"),
        ],
    )
    tickers = ["AAPL", "MSFT", "GOOG", "META"]
    scorer = Scorer(store)
    result = scorer.score(tickers=tickers, model=model)
    assert len(result) == 4
    assert "composite_score" in result.columns
    assert "ticker" in result.columns
    # META should rank high: low PE + high momentum
    assert result.iloc[0]["ticker"] == "META"


def test_scorer_handles_missing_data(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_scoring_db(store)
    model = ModelConfig(
        name="test-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
            FactorConfig(name="sentiment", metric="news_sentiment_30d", weight=0.5, direction="higher_is_better"),
        ],
    )
    # Include a ticker not in DB
    scorer = Scorer(store)
    result = scorer.score(tickers=["AAPL", "UNKNOWN"], model=model)
    # UNKNOWN should be dropped, AAPL should remain
    assert "AAPL" in result["ticker"].values

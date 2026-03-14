import sys
from pathlib import Path

import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer


def test_custom_factor_loads_and_scores(tmp_path: Path):
    # Add fixtures dir to path so the custom module can be imported
    fixtures_dir = Path(__file__).parent / "fixtures"
    sys.path.insert(0, str(fixtures_dir))

    store = Store(tmp_path / "test.db")

    # Seed price data
    df = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [100.0, 105.0, 108.0],
        "high": [106.0, 110.0, 112.0],
        "low": [99.0, 104.0, 107.0],
        "close": [105.0, 108.0, 110.0],
        "volume": [1000000, 1100000, 1050000],
    })
    store.upsert_prices("TEST", df, source="test")

    model = ModelConfig(
        name="custom-test",
        factors=[
            FactorConfig(
                name="custom_momentum",
                type="python",
                module="sample_custom_factor",
                weight=1.0,
            ),
        ],
    )

    scorer = Scorer(store)
    result = scorer.score(tickers=["TEST"], model=model)
    assert len(result) == 1
    assert "composite_score" in result.columns

    sys.path.pop(0)

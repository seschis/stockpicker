import pandas as pd

from stockpicker.engine.reporter import Reporter


def test_factor_evaluation():
    reporter = Reporter()
    signals = pd.DataFrame({
        "ticker": ["A", "A", "B", "B", "C", "C"],
        "factor_name": ["value", "momentum", "value", "momentum", "value", "momentum"],
        "normalized_value": [0.8, 0.3, 0.4, 0.7, 0.6, 0.5],
        "composite_score": [0.55, 0.55, 0.55, 0.55, 0.55, 0.55],
    })
    returns = pd.Series({"A": 0.10, "B": 0.05, "C": -0.02})

    result = reporter.factor_evaluation(signals, returns)
    assert "factor_name" in result.columns
    assert "ic" in result.columns  # information coefficient
    assert len(result) == 2  # two factors

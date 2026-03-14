"""Sample custom factor for testing the plugin interface."""
import pandas as pd


def compute(ticker: str, data: pd.DataFrame) -> float:
    """Compute a simple momentum score from price data."""
    if data.empty or len(data) < 2:
        return 0.0
    closes = data["close"].values.astype(float)
    return float((closes[-1] - closes[0]) / closes[0])

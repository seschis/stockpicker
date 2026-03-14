from datetime import date
from stockpicker.sources.fred_source import FredSource


def test_fred_fetch_prices_returns_empty():
    source = FredSource()
    result = source.fetch_prices("DGS10", date(2024, 1, 1), date(2024, 1, 31))
    assert result.empty or list(result.columns) == ["date", "open", "high", "low", "close", "volume"]


def test_fred_fetch_news_returns_none():
    source = FredSource()
    result = source.fetch_news("DGS10", date(2024, 1, 1), date(2024, 1, 31))
    assert result is None

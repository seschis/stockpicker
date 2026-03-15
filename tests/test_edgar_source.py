from datetime import date

from stockpicker.sources.edgar_source import EdgarSource


def test_edgar_fetch_prices_returns_empty():
    source = EdgarSource()
    result = source.fetch_prices("AAPL", date(2024, 1, 1), date(2024, 1, 31))
    assert result.empty


def test_edgar_fetch_news_returns_none():
    source = EdgarSource()
    result = source.fetch_news("AAPL", date(2024, 1, 1), date(2024, 1, 31))
    assert result is None

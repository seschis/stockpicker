from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from stockpicker.sources.yfinance_source import YFinanceSource


def test_yfinance_fetch_prices_returns_correct_columns():
    mock_data = pd.DataFrame({
        "Open": [150.0, 151.0],
        "High": [155.0, 156.0],
        "Low": [149.0, 150.0],
        "Close": [154.0, 155.0],
        "Volume": [1000000, 1100000],
    }, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))

    with patch("stockpicker.sources.yfinance_source.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_data
        mock_yf.Ticker.return_value = mock_ticker

        source = YFinanceSource()
        result = source.fetch_prices("AAPL", date(2024, 1, 2), date(2024, 1, 3))

    assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(result) == 2


def test_yfinance_fetch_news_returns_none():
    source = YFinanceSource()
    result = source.fetch_news("AAPL", date(2024, 1, 1), date(2024, 1, 31))
    assert result is None


def test_yfinance_fetch_fundamentals_quarter_format():
    """Verify quarter strings are formatted as 'YYYY-QN'."""
    quarterly_data = pd.DataFrame(
        {"Total Revenue": [1e10, 1.1e10]},
        index=["Total Revenue", "Net Income"],
    )
    # Columns are timestamps representing quarter end dates
    quarterly_data = pd.DataFrame(
        {
            pd.Timestamp("2024-03-31"): [1e10, 5e8],
            pd.Timestamp("2024-06-30"): [1.1e10, 6e8],
        },
        index=["Total Revenue", "Net Income"],
    )

    mock_info = {"trailingEps": 5.0, "trailingPE": 28.0}

    with patch("stockpicker.sources.yfinance_source.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.quarterly_financials = quarterly_data
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker

        source = YFinanceSource()
        result = source.fetch_fundamentals("AAPL")

    assert len(result) == 2
    assert result.iloc[0]["quarter"] == "2024-Q1"
    assert result.iloc[1]["quarter"] == "2024-Q2"
    assert result.iloc[0]["revenue"] == 1e10
    assert result.iloc[1]["revenue"] == 1.1e10

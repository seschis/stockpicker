from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import requests

logger = logging.getLogger("stockpicker.sources.yahoo_direct")


class YahooDirectSource:
    """Yahoo Finance data via direct JSON API — no yfinance library needed."""

    CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    QUOTE_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._inject_truststore()

    @staticmethod
    def _inject_truststore() -> None:
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.info("Fetching prices for %s from %s to %s via Yahoo Direct", ticker, start, end)
        period1 = int(pd.Timestamp(str(start)).timestamp())  # pyright: ignore[reportAttributeAccessIssue]
        period2 = int(pd.Timestamp(str(end)).timestamp())  # pyright: ignore[reportAttributeAccessIssue]

        url = self.CHART_URL.format(symbol=ticker)
        params = {"period1": period1, "period2": period2, "interval": "1d"}

        try:
            resp = self._session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Yahoo Direct price fetch failed for %s: %s", ticker, e)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        result = data.get("chart", {}).get("result")
        if not result:
            error = data.get("chart", {}).get("error", {})
            logger.warning("No chart data for %s: %s", ticker, error.get("description", "unknown"))
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        timestamps = result[0].get("timestamp", [])
        quotes = result[0].get("indicators", {}).get("quote", [{}])[0]

        if not timestamps:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame({
            "date": [pd.Timestamp(ts, unit="s").strftime("%Y-%m-%d") for ts in timestamps],
            "open": quotes.get("open", []),
            "high": quotes.get("high", []),
            "low": quotes.get("low", []),
            "close": quotes.get("close", []),
            "volume": quotes.get("volume", []),
        })
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        logger.info("Got %d price rows for %s from Yahoo Direct", len(df), ticker)
        return df

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.info("Fetching fundamentals for %s via Yahoo Direct", ticker)
        url = self.QUOTE_URL.format(symbol=ticker)
        modules = "defaultKeyStatistics,financialData,incomeStatementHistoryQuarterly,earningsHistory"

        try:
            resp = self._session.get(url, params={"modules": modules}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Yahoo Direct fundamentals fetch failed for %s: %s", ticker, e)
            return pd.DataFrame()

        result = data.get("quoteSummary", {}).get("result")
        if not result:
            return pd.DataFrame()

        summary = result[0]
        key_stats = summary.get("defaultKeyStatistics", {})
        financials = summary.get("financialData", {})

        pe = _raw_val(key_stats.get("forwardPE") or key_stats.get("trailingPE"))
        eps = _raw_val(financials.get("revenuePerShare"))
        roe = _raw_val(financials.get("returnOnEquity"))
        debt_to_equity = _raw_val(financials.get("debtToEquity"))
        operating_margin = _raw_val(financials.get("operatingMargins"))
        gross_margin = _raw_val(financials.get("grossMargins"))
        fcf = _raw_val(financials.get("freeCashflow"))
        revenue = _raw_val(financials.get("totalRevenue"))

        quarterly = summary.get("incomeStatementHistoryQuarterly", {}).get(
            "incomeStatementHistory", []
        )

        if quarterly:
            records = []
            for stmt in quarterly[:4]:
                end_date = stmt.get("endDate", {})
                date_str = end_date.get("fmt", "")
                quarter_str = _date_to_quarter(date_str)
                q_revenue = _raw_val(stmt.get("totalRevenue"))
                q_gross = _raw_val(stmt.get("grossProfit"))
                q_margin = (q_gross / q_revenue) if q_revenue and q_gross else gross_margin
                records.append({
                    "quarter": quarter_str,
                    "eps": eps,
                    "pe_ratio": pe,
                    "revenue": q_revenue,
                    "gross_margin": q_margin,
                    "operating_margin": operating_margin,
                    "roe": roe,
                    "debt_to_equity": debt_to_equity,
                    "free_cash_flow": fcf,
                })
            return pd.DataFrame(records)

        return pd.DataFrame([{
            "quarter": "latest",
            "eps": eps,
            "pe_ratio": pe,
            "revenue": revenue,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "roe": roe,
            "debt_to_equity": debt_to_equity,
            "free_cash_flow": fcf,
        }])

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None


def _raw_val(field: dict | float | None) -> float | None:
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("raw")
    return float(field)


def _date_to_quarter(date_str: str) -> str:
    try:
        dt = pd.Timestamp(date_str)
        return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
    except Exception:
        return date_str

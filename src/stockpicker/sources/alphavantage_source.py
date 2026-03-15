from __future__ import annotations

import logging
import os
from datetime import date

import pandas as pd
import requests

logger = logging.getLogger("stockpicker.sources.alphavantage")

_DEFAULT_API_KEY = "demo"


class AlphaVantageSource:
    """Alpha Vantage data source. Free tier: 25 requests/day.

    Set ALPHAVANTAGE_API_KEY env var for full access (free key at
    https://www.alphavantage.co/support/#api-key).
    The 'demo' key works for fundamentals but not prices.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY", _DEFAULT_API_KEY)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "stockpicker/0.1"
        self._inject_truststore()

    @staticmethod
    def _inject_truststore() -> None:
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass

    def _get(self, params: dict) -> dict:
        params["apikey"] = self.api_key
        resp = self._session.get(self.BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "Error Message" in data:
            raise ValueError(data["Error Message"])
        if "Information" in data and "Time Series" not in str(list(data.keys())):
            logger.warning("Alpha Vantage: %s", data["Information"])
        return data

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.info("Fetching prices for %s via Alpha Vantage", ticker)
        try:
            data = self._get({
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
            })
        except Exception as e:
            logger.error("Alpha Vantage price fetch failed: %s", e)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        ts = data.get("Time Series (Daily)", {})
        if not ts:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        records = []
        start_str, end_str = str(start), str(end)
        for dt, vals in ts.items():
            if start_str <= dt <= end_str:
                records.append({
                    "date": dt,
                    "open": float(vals["1. open"]),
                    "high": float(vals["2. high"]),
                    "low": float(vals["3. low"]),
                    "close": float(vals["4. close"]),
                    "volume": int(vals["5. volume"]),
                })

        if not records:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
        logger.info("Got %d price rows for %s from Alpha Vantage", len(df), ticker)
        return df

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.info("Fetching fundamentals for %s via Alpha Vantage", ticker)
        try:
            overview = self._get({"function": "OVERVIEW", "symbol": ticker})
        except Exception as e:
            logger.error("Alpha Vantage overview fetch failed: %s", e)
            return pd.DataFrame()

        if "Symbol" not in overview:
            return pd.DataFrame()

        try:
            income = self._get({"function": "INCOME_STATEMENT", "symbol": ticker})
        except Exception:
            income = {}

        quarterly_reports = income.get("quarterlyReports", [])

        pe = _safe_float(overview.get("PERatio"))
        eps = _safe_float(overview.get("EPS"))
        roe = _safe_float(overview.get("ReturnOnEquityTTM"))
        debt_to_equity = _safe_float(overview.get("DebtToEquityRatio"))
        operating_margin = _safe_float(overview.get("OperatingMarginTTM"))
        gross_margin_ratio = _safe_float(overview.get("GrossProfitTTM"))
        fcf = _safe_float(overview.get("FreeCashFlow"))

        if quarterly_reports:
            records = []
            for qr in quarterly_reports[:4]:
                fiscal_date = qr.get("fiscalDateEnding", "")
                quarter_str = _date_to_quarter(fiscal_date)
                revenue = _safe_float(qr.get("totalRevenue"))
                gross_profit = _safe_float(qr.get("grossProfit"))
                gross_margin = (gross_profit / revenue) if revenue and gross_profit else gross_margin_ratio
                records.append({
                    "quarter": quarter_str,
                    "eps": eps,
                    "pe_ratio": pe,
                    "revenue": revenue,
                    "gross_margin": gross_margin,
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
            "revenue": _safe_float(overview.get("RevenueTTM")),
            "gross_margin": gross_margin_ratio,
            "operating_margin": operating_margin,
            "roe": roe,
            "debt_to_equity": debt_to_equity,
            "free_cash_flow": fcf,
        }])

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None


def _safe_float(val: str | None) -> float | None:
    if val is None or val in ("None", "-", ""):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _date_to_quarter(date_str: str) -> str:
    try:
        dt = pd.Timestamp(date_str)
        return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
    except Exception:
        return date_str

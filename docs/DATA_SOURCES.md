# Data Sources

Stockpicker ingests data from multiple sources in a fallback chain. Each source is tried in order — if one fails (rate limit, network error, missing data), the next source picks up. Prices and fundamentals are fetched independently, so a source can contribute prices even if it doesn't provide fundamentals.

## Source Priority

```
stooq → yahoo_direct → alphavantage → yfinance
```

| Source | Prices | Fundamentals | Auth | Rate Limits |
|--------|--------|-------------|------|-------------|
| Stooq | Yes | No | None | None observed |
| Yahoo Direct | Yes | Yes | None | Aggressive (429s) |
| Alpha Vantage | Yes | Yes | API key (free tier) | 25 req/day (free) |
| yfinance | Yes | Yes | None | Aggressive (429s) |

## Source Details

### Stooq (primary for prices)

**Why it's first:** Stooq is the most reliable source for historical US stock prices. It requires no API key, has no observed rate limits, and returns clean daily OHLCV data via a simple CSV endpoint. It covers US equities (append `.us` to the ticker) with data going back years.

**Limitations:** No fundamentals, no news, no international coverage outside major markets. Serves prices only.

**Implementation:** Direct HTTP GET to `stooq.com/q/d/l/` which returns CSV. No library dependency beyond `urllib`.

### Yahoo Direct (secondary)

**Why it's second:** Yahoo Finance has the broadest coverage — prices, quarterly fundamentals, and key statistics — all without an API key. We use the JSON chart API (`query2.finance.yahoo.com`) directly rather than the `yfinance` Python library, which avoids the library's auth/cookie overhead.

**Limitations:** Yahoo aggressively rate-limits requests (HTTP 429). After a burst of requests, it can block for minutes. This makes it unreliable as a primary source but valuable as a fallback that fills in fundamentals when Stooq handles prices.

**Implementation:** Uses `requests` with a browser User-Agent. Prices come from `/v8/finance/chart/`, fundamentals from `/v10/finance/quoteSummary/`.

### Alpha Vantage (tertiary)

**Why it's third:** Alpha Vantage provides high-quality fundamentals (quarterly income statements, PE, EPS, ROE, margins) and full daily price history. However, the free tier is limited to 25 API calls per day, so it's positioned after sources that don't have this hard cap.

**Limitations:** The free API key allows 25 requests/day — roughly 6 tickers if fetching both prices and fundamentals. The `demo` key only works for select tickers (IBM, etc.) and is unsuitable for real use. A free personal key takes 20 seconds to obtain at https://www.alphavantage.co/support/#api-key.

**Configuration:** Set the `ALPHAVANTAGE_API_KEY` environment variable. Falls back to the `demo` key if unset.

**Implementation:** REST API returning JSON. Uses `requests` with `truststore` for corporate SSL proxy compatibility.

### yfinance (last resort)

**Why it's last:** The `yfinance` Python library wraps Yahoo Finance with additional features (cookie management, auto-adjust, etc.) but is the most prone to rate limiting and breakage. It's kept as a last-resort fallback — if all other sources fail, yfinance may succeed if Yahoo's rate limiter has cooled down.

**Limitations:** Same Yahoo rate limits as Yahoo Direct, plus library-level issues (broken auth flows, version incompatibilities). On Python 3.13+, some dependent libraries have compatibility issues.

**Implementation:** Uses the `yfinance` library (`yf.Ticker`). Prices via `.history()`, fundamentals via `.quarterly_financials` and `.info`.

## SSL / Corporate Proxy Note

Alpha Vantage and Yahoo Direct use `truststore` to handle corporate SSL inspection proxies (e.g., Netskope, Zscaler). If you're on a corporate network and see SSL errors, ensure `truststore` is installed:

```bash
uv add truststore
```

Stooq works without this because its initial connection uses HTTP.

## Adding a New Source

1. Create a class in `src/stockpicker/sources/` implementing `fetch_prices()`, `fetch_fundamentals()`, and `fetch_news()` (see `base.py` for the protocol).
2. Add it to the `sources` dict in `src/stockpicker/cli/ingest.py`.
3. Position it in the dict based on reliability — sources are tried in insertion order.

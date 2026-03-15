# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the confirmed bugs and code quality issues from the codebase review — financial calculation correctness, division-by-zero guards, config validation, bulk DB performance, and encapsulation.

**Architecture:** Targeted fixes across 5 modules. Each task is independent. The golden-file regression test expected values will need regeneration after the Sortino fix.

**Tech Stack:** Python 3.12+, Pydantic v2, NumPy, pandas, SQLite

---

## Chunk 1: Financial Calculation Fixes + Config Validation

### Task 1: Fix Sortino ratio calculation

The Sortino ratio should use downside deviation `sqrt(mean(min(r, 0)^2))`, not `std(negative_returns)`. This bug exists in two places.

**Files:**
- Modify: `src/stockpicker/engine/backtester.py:178-179`
- Modify: `src/stockpicker/engine/reporter.py:28-30`
- Modify: `tests/fixtures/golden_backtest_expected.json` (regenerate)

- [ ] **Step 1: Fix Sortino in backtester.py**

Replace lines 178-179:
```python
# Old:
sortino_denom = np.std(returns[returns < 0]) if np.any(returns < 0) else 1e-10
sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

# New:
downside = np.minimum(returns, 0)
sortino_denom = np.sqrt(np.mean(downside ** 2)) if len(returns) > 0 else 1e-10
sortino = (np.mean(returns) / sortino_denom * np.sqrt(252)) if sortino_denom > 1e-10 else 0.0
```

- [ ] **Step 2: Fix Sortino in reporter.py**

Replace lines 28-30:
```python
# Old:
neg_returns = returns[returns < 0]
sortino_denom = np.std(neg_returns) if len(neg_returns) > 0 else 1e-10
sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

# New:
downside = np.minimum(returns, 0)
sortino_denom = np.sqrt(np.mean(downside ** 2)) if len(returns) > 0 else 1e-10
sortino = (np.mean(returns) / sortino_denom * np.sqrt(252)) if sortino_denom > 1e-10 else 0.0
```

- [ ] **Step 3: Run tests, regenerate golden file**

Delete `tests/fixtures/golden_backtest_expected.json`, run tests to regenerate, verify all pass.

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All pass, golden file regenerated with corrected Sortino values.

- [ ] **Step 4: Commit**

```bash
git add src/stockpicker/engine/backtester.py src/stockpicker/engine/reporter.py tests/fixtures/golden_backtest_expected.json
git commit -m "fix: correct Sortino ratio to use downside deviation"
```

---

### Task 2: Fix market cap formula in MetricsComputer

`last_price / eps * eps * pe * 1e6` simplifies to `last_price * pe * 1e6` which is wrong. Without shares outstanding data, the best estimate is `pe * eps` = price (circular). The practical fix: use `pe_ratio * eps * avg_volume` as a rough proxy until a real data source is added, or just store None when we can't compute it properly.

**Files:**
- Modify: `src/stockpicker/engine/metrics_computer.py:34-40`

- [ ] **Step 1: Fix the formula**

Replace the market cap block:
```python
# Old:
market_cap = None
if not fund.empty:
    pe = fund.iloc[-1].get("pe_ratio")
    eps = fund.iloc[-1].get("eps")
    if pe and eps and pe > 0 and eps > 0:
        market_cap = last_price / eps * eps * pe * 1e6  # rough estimate

# New:
market_cap = None  # Requires shares_outstanding from data source; not estimable from PE/EPS alone
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_metrics_computer.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/stockpicker/engine/metrics_computer.py
git commit -m "fix: remove nonsensical market cap formula (needs shares_outstanding data)"
```

---

### Task 3: Fix delisted stock exit price in backtester

When a stock has no price on a given day, it exits at entry_price instead of last known price. This masks losses.

**Files:**
- Modify: `src/stockpicker/engine/backtester.py:80-83`

- [ ] **Step 1: Fix delisted exit to use last known price**

Replace:
```python
if current_price is None:
    # Delisted or gap — force exit at last known price
    to_sell.append((ticker, pos.entry_price, "DELISTED"))
    continue
```

With:
```python
if current_price is None:
    # Delisted or gap — exit at last known price from cache
    df = price_cache.get(ticker)
    last_known = float(df[df["date"] < date].iloc[-1]["close"]) if df is not None and not df[df["date"] < date].empty else pos.entry_price
    to_sell.append((ticker, last_known, "DELISTED"))
    continue
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_backtester.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/stockpicker/engine/backtester.py
git commit -m "fix: use last known price for delisted stock exits instead of entry price"
```

---

### Task 4: Fix win rate calculation in Reporter

The current code uses a dict `{ticker: trade}` which overwrites earlier buys for the same ticker. A ticker bought/sold multiple times only tracks the last buy.

**Files:**
- Modify: `src/stockpicker/engine/reporter.py:36-41`

- [ ] **Step 1: Fix win rate to pair trades chronologically**

Replace:
```python
# Win rate from trade pairs
buys = {t["ticker"]: t for t in trades if t["action"] == "BUY"}
sells = [t for t in trades if t["action"] == "SELL"]
wins = sum(1 for s in sells if s["ticker"] in buys and s["price"] > buys[s["ticker"]]["price"])
total_closed = len(sells)
win_rate = wins / total_closed if total_closed > 0 else 0.0
```

With:
```python
# Win rate from chronological trade pairs (FIFO matching)
buy_queues: dict[str, list[float]] = {}
wins = 0
total_closed = 0
for t in trades:
    if t["action"] == "BUY":
        buy_queues.setdefault(t["ticker"], []).append(t["price"])
    elif t["action"] == "SELL" and buy_queues.get(t["ticker"]):
        entry_price = buy_queues[t["ticker"]].pop(0)
        total_closed += 1
        if t["price"] > entry_price:
            wins += 1
win_rate = wins / total_closed if total_closed > 0 else 0.0
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_reporter.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/stockpicker/engine/reporter.py
git commit -m "fix: use FIFO matching for win rate calculation"
```

---

### Task 5: Add config validation for positive integers

**Files:**
- Modify: `src/stockpicker/config/models.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add validators**

Add `field_validator` for `top_n`, `hold_days`, `max_positions`:

In `BuyRules`:
```python
from pydantic import field_validator

@field_validator("top_n")
@classmethod
def top_n_positive(cls, v: int) -> int:
    if v < 1:
        raise ValueError("top_n must be >= 1")
    return v
```

In `SellRules`:
```python
@field_validator("hold_days")
@classmethod
def hold_days_positive(cls, v: int) -> int:
    if v < 1:
        raise ValueError("hold_days must be >= 1")
    return v
```

In `PortfolioRules`:
```python
@field_validator("max_positions")
@classmethod
def max_positions_positive(cls, v: int) -> int:
    if v < 1:
        raise ValueError("max_positions must be >= 1")
    return v
```

In `FactorConfig`:
```python
@field_validator("weight")
@classmethod
def weight_non_negative(cls, v: float) -> float:
    if v < 0:
        raise ValueError("weight must be >= 0")
    return v
```

- [ ] **Step 2: Add tests**

Add to `tests/test_config.py`:
```python
def test_buy_rules_top_n_must_be_positive():
    with pytest.raises(ValidationError):
        BuyRules(top_n=0)

def test_sell_rules_hold_days_must_be_positive():
    with pytest.raises(ValidationError):
        SellRules(hold_days=0)

def test_portfolio_max_positions_must_be_positive():
    with pytest.raises(ValidationError):
        PortfolioRules(max_positions=0)

def test_factor_weight_must_be_non_negative():
    with pytest.raises(ValidationError):
        FactorConfig(name="test", weight=-0.5)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/stockpicker/config/models.py tests/test_config.py
git commit -m "fix: add validation for positive integers and non-negative weights in config"
```

---

## Chunk 2: Performance + Encapsulation

### Task 6: Use executemany for bulk DB inserts

**Files:**
- Modify: `src/stockpicker/db/store.py:40-47, 61-73`

- [ ] **Step 1: Replace row-by-row inserts with executemany**

Replace `upsert_prices`:
```python
def upsert_prices(self, ticker: str, df: pd.DataFrame, source: str = "") -> None:
    rows = [
        (ticker, row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"]), source)
        for _, row in df.iterrows()
    ]
    self._conn.executemany(
        "INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close, volume, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    self._conn.commit()
```

Replace `upsert_fundamentals`:
```python
def upsert_fundamentals(self, ticker: str, df: pd.DataFrame, source: str = "") -> None:
    rows = [
        (
            ticker, row["quarter"], row.get("eps"), row.get("pe_ratio"), row.get("revenue"),
            row.get("gross_margin"), row.get("operating_margin"), row.get("roe"),
            row.get("debt_to_equity"), row.get("free_cash_flow"), source,
        )
        for _, row in df.iterrows()
    ]
    self._conn.executemany(
        "INSERT OR REPLACE INTO fundamentals "
        "(ticker, quarter, eps, pe_ratio, revenue, gross_margin, operating_margin, roe, debt_to_equity, free_cash_flow, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    self._conn.commit()
```

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_db.py tests/test_backtester.py tests/test_backtest_regression.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/stockpicker/db/store.py
git commit -m "perf: use executemany for bulk DB inserts"
```

---

### Task 7: Add Store methods for ticker_info and computed_metrics (fix encapsulation)

MetricsComputer and PaperTrader access `store._conn` directly. Add proper public methods.

**Files:**
- Modify: `src/stockpicker/db/store.py`
- Modify: `src/stockpicker/engine/metrics_computer.py`

- [ ] **Step 1: Add methods to Store**

Add to Store class:
```python
def upsert_ticker_info(self, ticker: str, market_cap: float | None, sector: str, country: str, avg_volume: float, last_price: float) -> None:
    self._conn.execute(
        "INSERT OR REPLACE INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ticker, market_cap, sector, country, avg_volume, last_price),
    )
    self._conn.commit()

def upsert_computed_metrics(self, ticker: str, price_return_90d: float | None, revenue_growth_yoy: float | None, news_sentiment_30d: float | None) -> None:
    self._conn.execute(
        "INSERT OR REPLACE INTO computed_metrics (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
        "VALUES (?, ?, ?, ?)",
        (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d),
    )
    self._conn.commit()
```

- [ ] **Step 2: Update MetricsComputer to use Store methods**

Replace direct `_conn` access with new methods.

- [ ] **Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/stockpicker/db/store.py src/stockpicker/engine/metrics_computer.py
git commit -m "refactor: add Store methods for ticker_info and computed_metrics"
```

---

### Task 8: Add division-by-zero guard in Sharpe ratio

**Files:**
- Modify: `src/stockpicker/engine/backtester.py:177`

- [ ] **Step 1: Already guarded — verify**

Line 177 already has `if np.std(returns) > 0 else 0.0`. Confirm reporter.py:27 has the same guard. (It does.)

No change needed. Skip.

---

### Task 9: Regenerate golden file and run full test suite

- [ ] **Step 1: Delete golden file and regenerate**

```bash
rm tests/fixtures/golden_backtest_expected.json
.venv/bin/python -m pytest tests/test_backtest_regression.py -v
```

- [ ] **Step 2: Run full suite**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: All PASS, no warnings.

# Stockpicker Architecture & Design

## Overview

Stockpicker is a modular CLI tool for stock analysis, factor-based scoring, backtesting, and paper trading. It's designed for quantitative investors who want to define trading strategies as YAML configuration, test them against historical data with point-in-time accuracy, and validate with simulated trading before committing capital.

**Key Philosophy:** Configuration-driven — no code changes required to experiment with new strategies, screens, and factor models.

---

## Project Structure

```
stock-research/
├── src/stockpicker/
│   ├── cli/                  # Typer CLI commands
│   ├── sources/              # Data source adapters (pluggable)
│   ├── factors/              # Factor computation (built-in + custom)
│   ├── engine/               # Core business logic
│   ├── db/                   # SQLite persistence + migrations
│   ├── config/               # Pydantic models + YAML loaders
│   └── logging_config.py     # Centralized logging setup
├── configs/                  # User-editable YAML configs
│   ├── screens/              # Stock screening criteria
│   ├── models/               # Factor model definitions
│   └── strategies/           # Trading strategy definitions
├── tests/                    # Comprehensive test suite
│   ├── test_*.py             # Unit and integration tests
│   └── fixtures/             # Test data and sample implementations
└── data/                     # Local SQLite database (gitignored)
```

---

## CLI Architecture

**Entry Point:** `stockpicker = "stockpicker.cli.main:app"` (defined in `pyproject.toml`)

The CLI is built with [Typer](https://typer.tiangolo.com/) and organized as a hierarchical application with six sub-commands:

| Command | Module | Purpose |
|---------|--------|---------|
| `ingest` | `cli/ingest.py` | Fetch prices/fundamentals from data sources into the database |
| `screen` | `cli/screen.py` | Apply filters to find tickers matching criteria |
| `score` | `cli/score.py` | Compute factor-based composite scores for screened tickers |
| `backtest` | `cli/backtest.py` | Run historical simulations of trading strategies |
| `paper` | `cli/paper.py` | Manage simulated (paper) trading sessions |
| `report` | `cli/report.py` | Generate performance reports and factor evaluations |

**Global options:**
- `--verbose / -v` — Set log level (once = INFO, twice = DEBUG)
- `--db-path` — Override default SQLite database location (`data/stockpicker.db`)

---

## Data Flow

### High-Level Pipeline

```
Ingest → Screen → Score → Backtest/Paper Trade → Report
```

### Ingest Flow

```
CLI: stockpicker ingest run AAPL MSFT --start 2024-01-01
  │
  ├─ Ingester.ingest()
  │   ├─ For each ticker:
  │   │   ├─ Check last ingested date in DB (incremental)
  │   │   └─ For each source (yfinance, edgar, fred):
  │   │       ├─ fetch_prices()
  │   │       ├─ fetch_fundamentals()
  │   │       └─ Store.upsert_*()
  │   └─ MetricsComputer.compute_all()
  │       └─ Populate ticker_info + computed_metrics tables
  └─ Return summary
```

**Incremental ingestion:** Only fetches data newer than what's already in the database, avoiding redundant API calls.

### Screen → Score → Backtest Flow

```
CLI: stockpicker backtest run --strategy momentum-value --start 2024-01-01 --end 2025-01-01
  │
  ├─ Load StrategyConfig → references screen + model configs
  ├─ Screener.screen(ScreenConfig)
  │   └─ Query ticker_info, apply filters → filtered tickers
  ├─ Scorer.score(tickers, ModelConfig)
  │   ├─ Fetch raw factor values from DB
  │   ├─ Normalize via percentile rank
  │   ├─ Compute composite_score = Σ(normalized_i × weight_i)
  │   └─ Return ranked tickers
  └─ Backtester.run(StrategyConfig, rankings, start, end)
      ├─ For each trading date:
      │   ├─ Check exits (stop loss, hold period)
      │   ├─ Execute buys (top_n, position sizing, slippage)
      │   └─ Record equity snapshot
      ├─ Compute metrics (Sharpe, Sortino, max drawdown)
      └─ Save trades to DB
```

### Paper Trading Flow

```
CLI: stockpicker paper run-cycle --session abc123 --strategy momentum-value
  │
  ├─ Ingester.ingest(tickers, today-7d, today)  # Fresh data
  ├─ Screener.screen() → filtered tickers
  ├─ Scorer.score() → ranked tickers
  └─ PaperTrader.run_cycle(session_id, rankings, prices, date, config)
      ├─ Query session state from DB
      ├─ Check sells / execute buys
      ├─ Update paper_sessions.cash + paper_positions
      └─ Save trades
```

Paper trading is **stateless by design** — all state lives in the database, enabling deployment via cron without a persistent server.

---

## Core Engines

### Screener (`engine/screener.py`)

Filters tickers from the `ticker_info` table based on `ScreenConfig`. Supported filter types:

- **Range:** `market_cap: [1e9, 50e9]` — between low and high
- **List:** `sector: ["Technology", "Healthcare"]` — must be in list
- **Min:** `avg_volume_min: 500000` — must exceed threshold

All filters are AND'd together.

### Scorer (`engine/scorer.py`)

Computes composite scores from factor models:

1. For each factor, fetch raw values (built-in from DB, or custom via plugin)
2. Normalize via percentile rank across tickers
3. Invert rank for `lower_is_better` factors (e.g., debt-to-equity)
4. Compute weighted sum → `composite_score`
5. Save signals to DB for later factor evaluation

### Backtester (`engine/backtester.py`)

Simulates historical trading with realistic constraints:

- **Point-in-time data** — uses closing prices, no look-ahead bias
- **Transaction costs** — commission + slippage (configurable in basis points)
- **Position sizing** — equal weight or score-weighted
- **Risk management** — stop losses, hold periods, max position size constraints
- **Metrics** — total return, annualized return, Sharpe ratio, Sortino ratio, max drawdown

### Paper Trader (`engine/paper_trader.py`)

Four operations: `start`, `status`, `run_cycle`, `stop`. Designed for cron-based execution — each cycle reads state from DB, executes trades, writes state back.

### Reporter (`engine/reporter.py`)

- **Strategy reports** — reconstructs equity curves from trades, computes performance metrics
- **Strategy comparison** — side-by-side metric comparison across strategies
- **Factor evaluation** — Information Coefficient (IC) per factor, measuring predictive power

---

## Data Sources

All sources implement the `DataSource` protocol (`sources/base.py`):

```python
class DataSource(Protocol):
    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...
    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame: ...
    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None: ...
```

Uses Python's `typing.Protocol` (structural subtyping) — no inheritance required.

| Source | Status | Data |
|--------|--------|------|
| `YFinanceSource` | Active | Prices (OHLCV) + quarterly fundamentals via yfinance |
| `EdgarSource` | Stub | SEC EDGAR quarterly filings (not yet implemented) |
| `FredSource` | Stub | FRED macro indicators (not yet implemented) |

---

## Configuration System

All configs are YAML files validated with **Pydantic v2** models (`config/models.py`).

### Config Hierarchy

```
StrategyConfig
├── name: str
├── screen: str          → references a ScreenConfig
├── model: str           → references a ModelConfig
└── rules: StrategyRules
    ├── buy: BuyRules       (top_n, position_size)
    ├── sell: SellRules     (hold_days, stop_loss)
    ├── portfolio: PortfolioRules (initial_capital, max_positions, max_position_pct)
    └── costs: CostRules    (commission_per_trade, slippage_bps)

ModelConfig
├── name: str
└── factors: list[FactorConfig]
    ├── name, metric, weight, direction
    ├── type: "builtin" | "python"
    └── module: str (for custom factors)

ScreenConfig
├── name: str
└── filters: dict[str, Any]
```

**Validation:** Factor weights must sum to 1.0 (±0.01), stop loss must be negative, etc.

---

## Factor System

### Built-in Factors (`factors/builtin.py`)

Mapped to database columns via `METRIC_SOURCES`:

| Factor | Source Table | Column |
|--------|-------------|--------|
| `pe_ratio`, `eps`, `revenue`, `gross_margin`, `operating_margin` | fundamentals | same |
| `roe` / `return_on_equity`, `debt_to_equity`, `free_cash_flow` | fundamentals | same |
| `price_return_90d`, `revenue_growth_yoy`, `news_sentiment_30d` | computed_metrics | same |

### Custom Factors (Plugin System)

Drop a Python module anywhere with a `compute()` function:

```python
# src/stockpicker/factors/custom/my_momentum.py
def compute(ticker: str, data: pd.DataFrame) -> float:
    closes = data["close"].values.astype(float)
    return float((closes[-1] - closes[0]) / closes[0])
```

Reference in model config:

```yaml
factors:
  - name: my_signal
    type: python
    module: stockpicker.factors.custom.my_momentum
    weight: 0.20
```

The scorer uses `importlib.import_module()` to dynamically load and call the `compute` function.

---

## Database Schema

SQLite with WAL mode. Migrations auto-run on `Store.__init__()`.

### Tables

| Table | Purpose |
|-------|---------|
| `prices` | OHLCV price data (ticker, date, open, high, low, close, volume, source) |
| `fundamentals` | Quarterly metrics (ticker, quarter, eps, pe_ratio, revenue, margins, etc.) |
| `ticker_info` | Summary data for screening (market_cap, sector, country, avg_volume, last_price) |
| `computed_metrics` | Derived metrics (price_return_90d, revenue_growth_yoy, news_sentiment_30d) |
| `signals` | Factor scores per ticker/date/model (raw_value, normalized_value, composite_score) |
| `trades` | All executed trades — backtest + paper (action, price, shares, commission, slippage) |
| `paper_sessions` | Paper trading session state (strategy_id, status, cash) |
| `paper_positions` | Open paper trading positions (ticker, shares, entry_price, entry_date) |
| `schema_version` | Tracks applied migrations |

Migrations are stored in `db/migrations/` as numbered SQL files (001_initial.sql through 004_paper_trading.sql).

---

## Testing

### Test Organization

| Test File | Scope |
|-----------|-------|
| `test_config.py` | Pydantic model validation |
| `test_db.py` | Store upsert/get operations, migrations |
| `test_sources.py` | Data source protocol compliance |
| `test_ingest.py` | Incremental ingestion logic |
| `test_screener.py` | Filter application (range, list, min) |
| `test_scorer.py` | Factor normalization, custom factor loading |
| `test_backtester.py` | Trade logic, metrics computation |
| `test_paper_trader.py` | Session state management |
| `test_reporter.py` | Equity curve reconstruction, metrics |
| `test_factor_evaluation.py` | Information Coefficient calculation |
| `test_custom_factor.py` | Custom factor plugin loading |
| `test_metrics_computer.py` | Derived metrics computation |
| `test_cli_integration.py` | Full CLI workflows via CliRunner |
| `test_integration.py` | End-to-end pipeline |
| `test_backtest_regression.py` | Golden-file regression test |

### Testing Patterns

- **Unit tests:** Mocked/synthetic data, in-memory SQLite
- **Integration tests:** Seeded databases, real engine pipelines
- **CLI tests:** `typer.testing.CliRunner` for command-level testing
- **Regression tests:** Golden files lock in expected backtester outputs

---

## Key Design Decisions

1. **Protocol-based data sources** — structural subtyping over inheritance, enabling loose coupling and easy testing
2. **Configuration-driven strategies** — YAML configs compose screens, models, and rules without code changes
3. **Incremental ingestion** — avoids redundant API calls by tracking last-ingested dates per ticker
4. **Stateless paper trading** — all state in SQLite, enabling cron-based execution without a running server
5. **Dynamic factor plugins** — `importlib` loading of custom Python modules for extensibility
6. **Pydantic validation** — catches configuration errors (invalid weights, missing fields) at load time
7. **SQLite with WAL** — simple, file-based persistence with concurrent read support
8. **Golden-file regression tests** — locks in backtester behavior to catch unintended changes

---

## Extension Guide

### Adding a New Data Source

1. Create `src/stockpicker/sources/my_source.py` implementing the `DataSource` protocol
2. Register in `cli/ingest.py` sources dict
3. Add tests following the `test_sources.py` pattern

### Adding a New Built-in Factor

1. Add to `METRIC_SOURCES` in `factors/builtin.py`
2. Ensure data is populated (via `MetricsComputer` or a data source)
3. Reference in model YAML config

### Adding a Custom Factor

1. Create module with `compute(ticker: str, data: pd.DataFrame) -> float`
2. Reference in model YAML with `type: python` and `module: <import.path>`

### Adding a New Strategy

1. Create screen config: `configs/screens/my-screen.yaml`
2. Create model config: `configs/models/my-model.yaml`
3. Create strategy config: `configs/strategies/my-strategy.yaml`
4. Backtest: `stockpicker backtest run --strategy my-strategy --start 2024-01-01 --end 2025-01-01`
5. Paper trade: `stockpicker paper start --strategy my-strategy`

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `typer` | >=0.15.0 | CLI framework |
| `pandas` | >=2.2.0 | Data manipulation |
| `numpy` | >=2.0.0 | Numerical computations |
| `pydantic` | >=2.10.0 | Config validation |
| `pyyaml` | >=6.0.0 | YAML parsing |
| `rich` | >=13.0.0 | Terminal output styling |
| `yfinance` | >=1.2.0 | Stock data API |

**Python:** >=3.12

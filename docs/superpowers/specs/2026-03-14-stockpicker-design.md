# Stockpicker — Design Specification

## Overview

Stockpicker is a modular Python CLI tool for stock analysis, multi-factor scoring, backtesting, and paper trading. It helps identify investment opportunities in public equities through quantitative analysis with optional qualitative (sentiment) signals.

**Target user:** Software engineer with ML/data science background, using coding agents for development.

**Investment context:** ~$100K for growth, short-to-medium term strategies (days to months), manual trade execution initially with architecture supporting future broker integration.

**3-month success criteria:** Working pipeline with at least one backtested strategy running in paper trading.

## Architecture

Modular pipeline with six CLI subcommands connected by a shared local database:

```
[Data Sources] → ingest → [Local DB] → screen → score → backtest → paper → report
```

Each stage is an independent module: independently testable, replaceable, and composable via scripting. Business logic lives in `engine/`, decoupled from the CLI layer in `cli/`.

**Stack:**
- Language: Python
- Project management: uv
- CLI framework: Typer
- Database: SQLite (migratable to Postgres/TimescaleDB later)
- Data/ML: pandas, numpy, scikit-learn, PyTorch
- Visualization: matplotlib (optional PNG export), ASCII charts for terminal
- Configuration: YAML

## Data Layer

### Data Source Abstraction

Each data source implements a common interface:

```python
class DataSource:
    def fetch_prices(ticker, start, end) → DataFrame
    def fetch_fundamentals(ticker) → DataFrame
    def fetch_news(ticker, start, end) → DataFrame
```

Adding a new data source means writing one class. Everything downstream is unaffected.

**Starting sources (free):**
- **yfinance** — price/volume data, basic fundamentals
- **SEC EDGAR** — quarterly/annual filings, insider transactions
- **FRED** — macro indicators (interest rates, GDP, inflation)
- **News TBD** — RSS feeds or free news API for sentiment

**Paid sources (future):** Alpha Vantage, Polygon.io, Financial Modeling Prep, Tiingo, etc. Data spend treated as a business expense — justified by measurable improvement in strategy performance.

### Database Schema (SQLite)

| Table | Contents | Key |
|-------|----------|-----|
| `prices` | OHLCV daily/intraday data | (ticker, date) |
| `fundamentals` | EPS, P/E, revenue, margins, etc. | (ticker, quarter) |
| `signals` | Computed factor scores, sentiment scores | (ticker, date, model_id) |
| `trades` | Backtest and paper trade records (entry/exit, P&L) | (trade_id, strategy_id) |
| `models` | Factor model and strategy registry with configs and performance | (model_id) |

### Ingestion Behavior

- `stockpicker ingest` is incremental — only fetches data since last run
- Handles rate limiting per source (sleeps, retries)
- Stores raw data; computed signals produced during the `score` phase
- Can ingest a specific ticker, a watchlist, or the full universe (configurable)

## Screening

`stockpicker screen` filters the stock universe using declarative YAML criteria:

```yaml
# configs/screens/us-midcap-tech.yaml
name: US Mid-Cap Tech
filters:
  market_cap: [2B, 10B]
  sector: [Technology]
  country: US
  avg_volume_min: 500000
  price_min: 5.0
```

**Usage:** `stockpicker screen --config configs/screens/us-midcap-tech.yaml`

**Output:** List of tickers passing all filters, saved to DB and printed as a table. Supports chaining multiple screens and ad-hoc CLI flag overrides.

## Scoring

`stockpicker score` is the heart of the system. A factor model is a YAML config defining weighted factors:

```yaml
# configs/models/multi-factor-v1.yaml
name: multi-factor-v1
factors:
  - name: value
    metric: pe_ratio
    weight: 0.25
    direction: lower_is_better
  - name: growth
    metric: revenue_growth_yoy
    weight: 0.25
    direction: higher_is_better
  - name: momentum
    metric: price_return_90d
    weight: 0.20
    direction: higher_is_better
  - name: quality
    metric: return_on_equity
    weight: 0.15
    direction: higher_is_better
  - name: sentiment
    metric: news_sentiment_30d
    weight: 0.15
    direction: higher_is_better
```

**Scoring process:**
1. Each factor is normalized (z-score or percentile rank across the screened universe)
2. Factors are weighted per config
3. Combined into a composite score

**Custom factor support:** ML-based signals as first-class factors:

```yaml
  - name: custom_ml
    type: python
    module: factors.my_lstm_model
    weight: 0.20
```

Drop a Python file in `src/stockpicker/factors/custom/`, reference it from model YAML, and it participates in scoring alongside built-in metrics.

**Usage:** `stockpicker score --screen us-midcap-tech --model multi-factor-v1`

**Output:** Ranked list with composite scores and per-factor breakdowns.

## Backtesting

`stockpicker backtest` simulates a strategy against historical data. A strategy config ties together a screen, a model, and trading rules:

```yaml
# configs/strategies/momentum-value.yaml
name: momentum-value
screen: us-midcap-tech
model: multi-factor-v1
rules:
  buy:
    top_n: 10
    position_size: equal
  sell:
    hold_days: 30
    stop_loss: -0.08
  portfolio:
    initial_capital: 100000
    max_positions: 10
    max_position_pct: 0.15
```

**Usage:** `stockpicker backtest --strategy momentum-value --start 2023-01-01 --end 2025-12-31`

**Output metrics:**
- Total return, annualized return
- Sharpe ratio, Sortino ratio
- Max drawdown, time to recovery
- Win rate, average win/loss
- Comparison against benchmark (e.g., SPY)
- Per-trade log

**Strategy comparison:** `stockpicker report --compare momentum-value,pure-value,pure-momentum`

## Paper Trading

`stockpicker paper` runs a strategy forward in real time with simulated capital.

**Commands:**
- `stockpicker paper start --strategy momentum-value` — begin paper trading
- `stockpicker paper status` — show current positions, P&L, pending signals
- `stockpicker paper stop` — end session, generate performance report

**Implementation:** A lightweight scheduler (cron job or daemon) that daily:
1. Runs `ingest` to pull fresh data
2. Runs `score` against current universe
3. Evaluates buy/sell rules against current paper positions
4. Logs simulated trades to the `trades` table
5. Outputs daily summary

No broker integration — simulated against real market prices.

## Reporting & Model Evaluation

`stockpicker report` closes the feedback loop.

**Three report types:**

### 1. Strategy Performance
`stockpicker report --strategy momentum-value`
- Equity curve, drawdown chart (ASCII terminal or PNG export)
- Key metrics table (Sharpe, returns, drawdown, win rate)
- Attribution breakdown: which factors contributed most

### 2. Strategy Comparison
`stockpicker report --compare momentum-value,pure-value,pure-momentum`
- Side-by-side metrics table
- Relative performance over time
- Statistical significance testing

### 3. Factor Evaluation
`stockpicker report --evaluate-factors --model multi-factor-v1 --period 90d`
- Per-factor return contribution
- Factor correlation matrix (detect redundancy)
- Information coefficient (predictiveness per factor)

This directly supports the goal of empirically testing whether sentiment adds alpha — compare models with and without the sentiment factor.

**Output formats:**
- Terminal tables and ASCII charts (default)
- CSV/JSON export
- PNG charts via matplotlib (optional)

## Project Structure

```
stockpicker/
├── pyproject.toml
├── src/
│   └── stockpicker/
│       ├── cli/                # Typer CLI commands
│       │   ├── ingest.py
│       │   ├── screen.py
│       │   ├── score.py
│       │   ├── backtest.py
│       │   ├── paper.py
│       │   └── report.py
│       ├── sources/            # data source adapters
│       │   ├── base.py         # DataSource interface
│       │   ├── yfinance.py
│       │   ├── edgar.py
│       │   └── fred.py
│       ├── factors/            # factor computation
│       │   ├── builtin.py      # standard metrics
│       │   └── custom/         # user-defined ML factors
│       ├── engine/             # core business logic
│       │   ├── screener.py
│       │   ├── scorer.py
│       │   ├── backtester.py
│       │   ├── paper_trader.py
│       │   └── reporter.py
│       ├── db/                 # database layer
│       │   ├── schema.py
│       │   └── store.py
│       └── config/             # config loading & validation
├── configs/
│   ├── sources.yaml            # data source configuration
│   ├── screens/                # screening criteria
│   ├── models/                 # factor model definitions
│   └── strategies/             # strategy definitions
├── tests/
└── data/                       # local SQLite DB, cached data
    └── stockpicker.db
```

**Key decisions:**
- `src` layout for proper Python packaging (`pip install -e .` / `uv pip install -e .`)
- Config separate from code — screens, models, strategies are YAML files, version-controllable
- `engine/` decoupled from `cli/` — testable, reusable if a web UI is added later
- `custom/` factors directory for drop-in ML model integration
- Managed with `uv` for fast dependency resolution and virtual environment management

## Future Extensions (Out of Scope)

These are explicitly deferred but the architecture supports them:
- Broker integration for automated/semi-automated trade execution
- Private investment analysis
- Long-term (multi-year) strategy support
- Web dashboard UI
- Paid data source integrations
- Real-time/intraday data streaming

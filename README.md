# Stockpicker

A modular CLI tool for stock analysis, multi-factor scoring, backtesting, and paper trading. Built for quantitative investors who want to define strategies as config, test them against historical data, and validate with paper trading before committing real capital.

## Quick Start

```bash
# Install
uv pip install -e .

# Ingest price data for some tickers
stockpicker ingest run AAPL MSFT GOOG NVDA META --start 2024-01-01

# Screen for mid-cap tech stocks
stockpicker screen run --config configs/screens/us-midcap-tech.yaml

# Score them with a multi-factor model
stockpicker score run --screen us-midcap-tech --model multi-factor-v1

# Backtest a strategy
stockpicker backtest run --strategy momentum-value --start 2024-01-01 --end 2025-01-01

# Start paper trading
stockpicker paper start --strategy momentum-value
```

## How It Works

Stockpicker is a pipeline of six commands, each doing one thing well:

```
ingest → screen → score → backtest → paper → report
```

All commands share a local SQLite database. Strategies, screens, and models are defined as YAML config files — no code changes needed to experiment.

### 1. Ingest

Pull price and fundamental data from configured sources. Ingestion is incremental — it only fetches data newer than what's already in the database.

```bash
# Ingest last year of data
stockpicker ingest run AAPL MSFT GOOG

# Ingest a specific date range
stockpicker ingest run AAPL --start 2023-06-01 --end 2024-06-01
```

Data sources:
- **yfinance** — price/volume data and basic fundamentals (active)
- **SEC EDGAR** — quarterly filings (stub, ready for implementation)
- **FRED** — macro indicators (stub, ready for implementation)

### 2. Screen

Filter the stock universe using declarative criteria.

```bash
stockpicker screen run --config configs/screens/us-midcap-tech.yaml
```

Example screen config (`configs/screens/us-midcap-tech.yaml`):

```yaml
name: US Mid-Cap Tech
filters:
  market_cap: [2000000000, 10000000000]
  sector: [Technology]
  country: US
  avg_volume_min: 500000
  price_min: 5.0
```

Supported filters:
- **Range filters:** `market_cap`, `avg_volume`, `last_price`, `pe_ratio` — value is `[low, high]`
- **List filters:** `sector`, `country` — value is a list of allowed values
- **Minimum filters:** `avg_volume_min`, `price_min` — value is a minimum threshold

### 3. Score

Apply a weighted multi-factor model to rank screened stocks. Each factor is normalized via percentile ranking across the universe, then combined into a composite score.

```bash
stockpicker score run --screen us-midcap-tech --model multi-factor-v1 --top 10
```

Example model config (`configs/models/multi-factor-v1.yaml`):

```yaml
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

Built-in metrics: `pe_ratio`, `eps`, `revenue`, `gross_margin`, `operating_margin`, `roe`/`return_on_equity`, `debt_to_equity`, `free_cash_flow`, `revenue_growth_yoy`, `price_return_90d`, `news_sentiment_30d`

**Custom factors:** You can plug in your own Python/ML models as factors:

```yaml
  - name: my_signal
    type: python
    module: factors.my_lstm_model
    weight: 0.20
```

The module must expose a `compute(ticker: str, data: DataFrame) -> float` function. Drop it in `src/stockpicker/factors/custom/`.

### 4. Backtest

Simulate a strategy against historical data with realistic transaction costs.

```bash
stockpicker backtest run --strategy momentum-value --start 2024-01-01 --end 2025-01-01
```

Example strategy config (`configs/strategies/momentum-value.yaml`):

```yaml
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
  costs:
    commission_per_trade: 0.0
    slippage_bps: 5
```

Output includes: total return, annualized return, Sharpe ratio, Sortino ratio, max drawdown, and a full trade log. The backtester uses point-in-time data only (no look-ahead bias).

### 5. Paper Trade

Run a strategy forward with simulated money to validate before committing real capital.

```bash
# Start a session
stockpicker paper start --strategy momentum-value

# Run one daily cycle (call this via cron at market close)
stockpicker paper run-cycle --session <session-id> --strategy momentum-value

# Check status
stockpicker paper status --session <session-id>

# Stop and finalize
stockpicker paper stop --session <session-id>
```

Paper trading state (positions, cash) lives in the database, not in a running process. The `run-cycle` command is stateless and designed to be invoked via cron (e.g., daily at 16:30 ET).

### 6. Report

Measure whether your strategies and factor models actually work.

```bash
# Strategy performance
stockpicker report strategy --strategy momentum-value

# Compare strategies side by side
stockpicker report compare --compare "momentum-value,pure-value,pure-momentum"

# Evaluate factor predictiveness
stockpicker report evaluate-factors --model multi-factor-v1 --period 90d
```

The factor evaluation report computes the information coefficient (IC) per factor, telling you which factors are actually predictive and which are noise.

## Project Structure

```
stockpicker/
├── src/stockpicker/
│   ├── cli/           # Typer CLI commands
│   ├── sources/       # Data source adapters (yfinance, EDGAR, FRED)
│   ├── factors/       # Factor computation (built-in + custom/)
│   ├── engine/        # Core business logic
│   ├── db/            # SQLite store + migrations
│   └── config/        # Pydantic models + YAML loader
├── configs/
│   ├── screens/       # Stock screening criteria
│   ├── models/        # Factor model definitions
│   └── strategies/    # Trading strategy definitions
├── tests/
└── data/              # Local database (gitignored)
```

## Configuration

All strategies, screens, and models are YAML files in `configs/`. Create new ones by copying the examples:

```bash
cp configs/screens/us-midcap-tech.yaml configs/screens/my-screen.yaml
cp configs/models/multi-factor-v1.yaml configs/models/my-model.yaml
cp configs/strategies/momentum-value.yaml configs/strategies/my-strategy.yaml
```

Edit the YAML, then run. No code changes needed.

## Development

```bash
# Install with dev dependencies
uv pip install -e .
uv add --dev pytest pytest-cov

# Run tests
uv run pytest tests/ -v

# Run with verbose logging
stockpicker -vv ingest run AAPL
```

## Adding a Data Source

Create a new file in `src/stockpicker/sources/` implementing the `DataSource` protocol:

```python
class MySource:
    def fetch_prices(self, ticker, start, end) -> DataFrame: ...
    def fetch_fundamentals(self, ticker) -> DataFrame: ...
    def fetch_news(self, ticker, start, end) -> DataFrame | None: ...
```

Then register it in `src/stockpicker/cli/ingest.py`.

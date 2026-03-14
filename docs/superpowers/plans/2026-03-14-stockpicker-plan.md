# Stockpicker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular Python CLI for stock analysis, multi-factor scoring, backtesting, and paper trading.

**Architecture:** Pipeline of six CLI subcommands (ingest, screen, score, backtest, paper, report) connected by a shared SQLite database. Business logic in `engine/`, CLI in `cli/`, data adapters in `sources/`, config validation via Pydantic.

**Tech Stack:** Python 3.12+, uv, Typer, SQLite, Pydantic, pandas, numpy, yfinance, pytest

---

## Chunk 1: Project Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/stockpicker/__init__.py`
- Create: `src/stockpicker/cli/__init__.py`
- Create: `src/stockpicker/cli/main.py`

- [ ] **Step 1: Initialize project with uv**

```bash
cd /Users/shaneschisler/projects/stock-research
uv init --lib --name stockpicker
```

This creates `pyproject.toml` and `src/stockpicker/__init__.py`.

- [ ] **Step 2: Update pyproject.toml with dependencies and CLI entry point**

Replace the generated `pyproject.toml` with:

```toml
[project]
name = "stockpicker"
version = "0.1.0"
description = "Modular CLI for stock analysis, scoring, backtesting, and paper trading"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.15.0",
    "pandas>=2.2.0",
    "numpy>=2.0.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.0",
    "rich>=13.0.0",
]

[project.scripts]
stockpicker = "stockpicker.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 3: Add dev dependencies**

```bash
uv add --dev pytest pytest-cov
```

- [ ] **Step 4: Create CLI entry point with Typer**

Create `src/stockpicker/cli/__init__.py` (empty file).

Create `src/stockpicker/cli/main.py`:

```python
import typer

app = typer.Typer(
    name="stockpicker",
    help="Stock analysis, scoring, backtesting, and paper trading CLI.",
)


@app.callback()
def main(
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
) -> None:
    """Stockpicker CLI."""
    pass
```

- [ ] **Step 5: Create directory structure**

```bash
mkdir -p src/stockpicker/{sources,factors/custom,engine,db/migrations,config}
mkdir -p configs/{screens,models,strategies}
mkdir -p tests/fixtures
mkdir -p data/logs
touch src/stockpicker/sources/__init__.py
touch src/stockpicker/factors/__init__.py
touch src/stockpicker/factors/custom/__init__.py
touch src/stockpicker/engine/__init__.py
touch src/stockpicker/db/__init__.py
touch src/stockpicker/config/__init__.py
```

- [ ] **Step 6: Verify CLI installs and runs**

```bash
uv pip install -e .
uv run stockpicker --help
```

Expected: Help text showing "Stock analysis, scoring, backtesting, and paper trading CLI."

- [ ] **Step 7: Create .gitignore**

Create `.gitignore`:

```
data/
.superpowers/
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: scaffold stockpicker project with uv, Typer CLI entry point"
```

---

### Task 2: Logging Setup

**Files:**
- Create: `src/stockpicker/logging_config.py`
- Modify: `src/stockpicker/cli/main.py`
- Create: `tests/test_logging.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_logging.py`:

```python
from stockpicker.logging_config import setup_logging
import logging


def test_setup_logging_default_level():
    setup_logging(verbosity=0)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.WARNING


def test_setup_logging_verbose():
    setup_logging(verbosity=1)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.INFO


def test_setup_logging_very_verbose():
    setup_logging(verbosity=2)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.DEBUG
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_logging.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement logging_config.py**

Create `src/stockpicker/logging_config.py`:

```python
import logging
import sys
from pathlib import Path

LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


def setup_logging(verbosity: int = 0, log_dir: Path | None = None) -> None:
    level = LEVELS.get(verbosity, logging.DEBUG)
    logger = logging.getLogger("stockpicker")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(fmt)
    logger.addHandler(stderr_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_dir / "stockpicker.log", maxBytes=5_000_000, backupCount=3
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_logging.py -v
```

Expected: PASS

- [ ] **Step 5: Wire logging into CLI main callback**

Update `src/stockpicker/cli/main.py`:

```python
import typer

from stockpicker.logging_config import setup_logging

app = typer.Typer(
    name="stockpicker",
    help="Stock analysis, scoring, backtesting, and paper trading CLI.",
)


@app.callback()
def main(
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
) -> None:
    """Stockpicker CLI."""
    setup_logging(verbosity=verbose)
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add logging setup with verbosity flag"
```

---

### Task 3: Database Layer — Migrations & Store

**Files:**
- Create: `src/stockpicker/db/migrations/001_initial.sql`
- Create: `src/stockpicker/db/store.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write initial migration SQL**

Create `src/stockpicker/db/migrations/001_initial.sql`:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    eps REAL,
    pe_ratio REAL,
    revenue REAL,
    gross_margin REAL,
    operating_margin REAL,
    roe REAL,
    debt_to_equity REAL,
    free_cash_flow REAL,
    source TEXT,
    PRIMARY KEY (ticker, quarter)
);

CREATE TABLE IF NOT EXISTS signals (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    model_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    raw_value REAL,
    normalized_value REAL,
    composite_score REAL,
    PRIMARY KEY (ticker, date, model_id, run_id, factor_name)
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    session_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    date TEXT NOT NULL,
    price REAL NOT NULL,
    shares REAL NOT NULL,
    commission REAL DEFAULT 0.0,
    slippage REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    model_type TEXT NOT NULL,
    config_yaml TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
CREATE INDEX IF NOT EXISTS idx_signals_model ON signals(model_id, run_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id, session_id);
```

- [ ] **Step 2: Write failing test for store**

Create `tests/test_db.py`:

```python
import sqlite3
from pathlib import Path

from stockpicker.db.store import Store


def test_store_creates_db_and_runs_migrations(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store = Store(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = sorted(row[0] for row in cursor.fetchall())
    conn.close()
    assert "prices" in tables
    assert "fundamentals" in tables
    assert "signals" in tables
    assert "trades" in tables
    assert "models" in tables
    assert "schema_version" in tables


def test_store_migration_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.db"
    store1 = Store(db_path)
    store2 = Store(db_path)  # should not fail
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_store_upsert_prices(tmp_path: Path):
    import pandas as pd

    store = Store(tmp_path / "test.db")
    df = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03"],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    store.upsert_prices("AAPL", df, source="test")
    result = store.get_prices("AAPL")
    assert len(result) == 2
    assert result.iloc[0]["close"] == 154.0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement Store**

Create `src/stockpicker/db/store.py`:

```python
import logging
import sqlite3
from importlib import resources
from pathlib import Path

import pandas as pd

logger = logging.getLogger("stockpicker.db")


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._run_migrations()

    def _run_migrations(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        cursor = self._conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        current_version = cursor.fetchone()[0]

        migrations_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for mf in migration_files:
            version = int(mf.stem.split("_")[0])
            if version <= current_version:
                continue
            logger.info("Applying migration %s", mf.name)
            sql = mf.read_text()
            self._conn.executescript(sql)
            self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            self._conn.commit()

    def upsert_prices(self, ticker: str, df: pd.DataFrame, source: str = "") -> None:
        for _, row in df.iterrows():
            self._conn.execute(
                "INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close, volume, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ticker, row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"]), source),
            )
        self._conn.commit()

    def get_prices(self, ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM prices WHERE ticker = ?"
        params: list = [ticker]
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        query += " ORDER BY date"
        return pd.read_sql_query(query, self._conn, params=params)

    def upsert_fundamentals(self, ticker: str, df: pd.DataFrame, source: str = "") -> None:
        for _, row in df.iterrows():
            self._conn.execute(
                "INSERT OR REPLACE INTO fundamentals "
                "(ticker, quarter, eps, pe_ratio, revenue, gross_margin, operating_margin, roe, debt_to_equity, free_cash_flow, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ticker, row["quarter"], row.get("eps"), row.get("pe_ratio"), row.get("revenue"),
                    row.get("gross_margin"), row.get("operating_margin"), row.get("roe"),
                    row.get("debt_to_equity"), row.get("free_cash_flow"), source,
                ),
            )
        self._conn.commit()

    def get_fundamentals(self, ticker: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM fundamentals WHERE ticker = ? ORDER BY quarter", self._conn, params=[ticker]
        )

    def save_signals(self, records: list[dict]) -> None:
        for r in records:
            self._conn.execute(
                "INSERT OR REPLACE INTO signals "
                "(ticker, date, model_id, run_id, factor_name, raw_value, normalized_value, composite_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (r["ticker"], r["date"], r["model_id"], r["run_id"], r["factor_name"],
                 r.get("raw_value"), r.get("normalized_value"), r.get("composite_score")),
            )
        self._conn.commit()

    def save_trade(self, trade: dict) -> None:
        self._conn.execute(
            "INSERT INTO trades (strategy_id, session_type, session_id, ticker, action, date, price, shares, commission, slippage) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trade["strategy_id"], trade["session_type"], trade["session_id"], trade["ticker"],
             trade["action"], trade["date"], trade["price"], trade["shares"],
             trade.get("commission", 0.0), trade.get("slippage", 0.0)),
        )
        self._conn.commit()

    def get_trades(self, strategy_id: str | None = None, session_id: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM trades WHERE 1=1"
        params: list = []
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY date"
        return pd.read_sql_query(query, self._conn, params=params)

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_db.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add SQLite store with migration system"
```

---

### Task 4: Configuration Layer — Pydantic Models

**Files:**
- Create: `src/stockpicker/config/models.py`
- Create: `src/stockpicker/config/loader.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from stockpicker.config.models import ScreenConfig, FactorConfig, ModelConfig, StrategyConfig


def test_screen_config_valid():
    cfg = ScreenConfig(
        name="US Mid-Cap Tech",
        filters={"market_cap": [2_000_000_000, 10_000_000_000], "sector": ["Technology"]},
    )
    assert cfg.name == "US Mid-Cap Tech"


def test_model_config_weights_must_sum_to_one():
    with pytest.raises(ValidationError, match="weights must sum to 1.0"):
        ModelConfig(
            name="bad-model",
            factors=[
                FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
                FactorConfig(name="growth", metric="revenue_growth_yoy", weight=0.3, direction="higher_is_better"),
            ],
        )


def test_model_config_valid():
    cfg = ModelConfig(
        name="good-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.6, direction="lower_is_better"),
            FactorConfig(name="growth", metric="revenue_growth_yoy", weight=0.4, direction="higher_is_better"),
        ],
    )
    assert len(cfg.factors) == 2


def test_strategy_config_stop_loss_must_be_negative():
    with pytest.raises(ValidationError):
        StrategyConfig(
            name="bad",
            screen="test",
            model="test",
            rules={
                "buy": {"top_n": 10, "position_size": "equal"},
                "sell": {"hold_days": 30, "stop_loss": 0.08},
                "portfolio": {"initial_capital": 100000, "max_positions": 10, "max_position_pct": 0.15},
                "costs": {"commission_per_trade": 0.0, "slippage_bps": 5},
            },
        )
```

- [ ] **Step 2: Run tests to verify failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement config models**

Create `src/stockpicker/config/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class ScreenConfig(BaseModel):
    name: str
    filters: dict[str, Any]


class FactorConfig(BaseModel):
    name: str
    metric: str | None = None
    weight: float
    direction: Literal["higher_is_better", "lower_is_better"] = "higher_is_better"
    type: Literal["builtin", "python"] = "builtin"
    module: str | None = None


class ModelConfig(BaseModel):
    name: str
    factors: list[FactorConfig]

    @model_validator(mode="after")
    def check_weights(self) -> ModelConfig:
        total = sum(f.weight for f in self.factors)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Factor weights must sum to 1.0, got {total:.4f}")
        return self


class BuyRules(BaseModel):
    top_n: int = 10
    position_size: Literal["equal", "score_weighted"] = "equal"


class SellRules(BaseModel):
    hold_days: int = 30
    stop_loss: float = -0.08

    @model_validator(mode="after")
    def check_stop_loss(self) -> SellRules:
        if self.stop_loss >= 0:
            raise ValueError("stop_loss must be negative")
        return self


class PortfolioRules(BaseModel):
    initial_capital: float = 100_000.0
    max_positions: int = 10
    max_position_pct: float = 0.15

    @model_validator(mode="after")
    def check_pct(self) -> PortfolioRules:
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be between 0 and 1")
        return self


class CostRules(BaseModel):
    commission_per_trade: float = 0.0
    slippage_bps: float = 5.0


class StrategyRules(BaseModel):
    buy: BuyRules = BuyRules()
    sell: SellRules = SellRules()
    portfolio: PortfolioRules = PortfolioRules()
    costs: CostRules = CostRules()


class StrategyConfig(BaseModel):
    name: str
    screen: str
    model: str
    rules: StrategyRules
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS

- [ ] **Step 5: Implement YAML config loader**

Create `src/stockpicker/config/loader.py`:

```python
import logging
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from stockpicker.config.models import ModelConfig, ScreenConfig, StrategyConfig

logger = logging.getLogger("stockpicker.config")

T = TypeVar("T", bound=BaseModel)

CONFIG_TYPES = {
    "screen": ScreenConfig,
    "model": ModelConfig,
    "strategy": StrategyConfig,
}


def load_yaml(path: Path, config_type: type[T]) -> T:
    logger.debug("Loading config from %s", path)
    with open(path) as f:
        data = yaml.safe_load(f)
    return config_type.model_validate(data)


def load_screen(path: Path) -> ScreenConfig:
    return load_yaml(path, ScreenConfig)


def load_model(path: Path) -> ModelConfig:
    return load_yaml(path, ModelConfig)


def load_strategy(path: Path) -> StrategyConfig:
    return load_yaml(path, StrategyConfig)
```

- [ ] **Step 6: Add YAML loader test**

Append to `tests/test_config.py`:

```python
from pathlib import Path
from stockpicker.config.loader import load_screen, load_model


def test_load_screen_from_yaml(tmp_path: Path):
    yaml_content = """
name: Test Screen
filters:
  market_cap: [1000000000, 5000000000]
  sector: [Technology]
"""
    p = tmp_path / "screen.yaml"
    p.write_text(yaml_content)
    cfg = load_screen(p)
    assert cfg.name == "Test Screen"


def test_load_model_from_yaml(tmp_path: Path):
    yaml_content = """
name: test-model
factors:
  - name: value
    metric: pe_ratio
    weight: 0.5
    direction: lower_is_better
  - name: growth
    metric: revenue_growth_yoy
    weight: 0.5
    direction: higher_is_better
"""
    p = tmp_path / "model.yaml"
    p.write_text(yaml_content)
    cfg = load_model(p)
    assert cfg.name == "test-model"
    assert len(cfg.factors) == 2
```

- [ ] **Step 7: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add Pydantic config models and YAML loader with validation"
```

---

## Chunk 2: Data Sources & Ingestion

### Task 5: Data Source Protocol & yfinance Adapter

**Files:**
- Create: `src/stockpicker/sources/base.py`
- Create: `src/stockpicker/sources/yfinance_source.py`
- Create: `tests/test_sources.py`
- Create: `tests/fixtures/aapl_prices.csv`

- [ ] **Step 1: Add yfinance dependency**

```bash
uv add yfinance
```

- [ ] **Step 2: Write the DataSource protocol**

Create `src/stockpicker/sources/base.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


class DataSource(Protocol):
    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """Returns DataFrame with columns: date, open, high, low, close, volume"""
        ...

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        """Returns DataFrame with columns: quarter, eps, pe_ratio, revenue,
        gross_margin, operating_margin, roe, debt_to_equity, free_cash_flow"""
        ...

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        """Returns DataFrame with columns: date, headline, source, sentiment_score.
        Returns None if the source does not support news."""
        ...
```

- [ ] **Step 3: Create fixture data for testing**

Create `tests/fixtures/aapl_prices.csv`:

```csv
date,open,high,low,close,volume
2024-01-02,150.00,155.00,149.00,154.00,1000000
2024-01-03,154.00,156.00,153.00,155.50,1100000
2024-01-04,155.50,157.00,154.00,156.00,950000
2024-01-05,156.00,158.00,155.00,157.50,1050000
2024-01-08,157.00,159.00,156.50,158.00,980000
2024-01-09,158.00,160.00,157.00,159.50,1020000
2024-01-10,159.00,161.00,158.50,160.00,1100000
2024-01-11,160.00,162.00,159.00,161.50,1150000
2024-01-12,161.00,163.00,160.50,162.00,970000
2024-01-15,162.00,164.00,161.00,163.50,1080000
```

- [ ] **Step 4: Write failing test for yfinance adapter**

Create `tests/test_sources.py`:

```python
from datetime import date
from unittest.mock import patch, MagicMock

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
```

- [ ] **Step 5: Run tests to verify failure**

```bash
uv run pytest tests/test_sources.py -v
```

Expected: FAIL

- [ ] **Step 6: Implement YFinanceSource**

Create `src/stockpicker/sources/yfinance_source.py`:

```python
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import yfinance as yf

logger = logging.getLogger("stockpicker.sources.yfinance")


class YFinanceSource:
    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.info("Fetching prices for %s from %s to %s", ticker, start, end)
        t = yf.Ticker(ticker)
        hist = t.history(start=str(start), end=str(end), auto_adjust=False)
        if hist.empty:
            logger.warning("No price data returned for %s", ticker)
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df["date"] = df.index.strftime("%Y-%m-%d")
        df = df.reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume"]]

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.info("Fetching fundamentals for %s", ticker)
        t = yf.Ticker(ticker)
        info = t.info
        quarterly = t.quarterly_financials

        if quarterly.empty:
            logger.warning("No fundamental data for %s", ticker)
            return pd.DataFrame(columns=[
                "quarter", "eps", "pe_ratio", "revenue", "gross_margin",
                "operating_margin", "roe", "debt_to_equity", "free_cash_flow",
            ])

        records = []
        for col in quarterly.columns:
            quarter_str = col.strftime("%Y-Q%q") if hasattr(col, "strftime") else str(col)
            records.append({
                "quarter": quarter_str,
                "eps": info.get("trailingEps"),
                "pe_ratio": info.get("trailingPE"),
                "revenue": quarterly.get(col, {}).get("Total Revenue"),
                "gross_margin": info.get("grossMargins"),
                "operating_margin": info.get("operatingMargins"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"),
            })
        return pd.DataFrame(records)

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/test_sources.py -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add DataSource protocol and yfinance adapter"
```

---

### Task 6: Ingest CLI Command

**Files:**
- Create: `src/stockpicker/engine/ingester.py`
- Create: `src/stockpicker/cli/ingest.py`
- Modify: `src/stockpicker/cli/main.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Write failing test for ingester engine**

Create `tests/test_ingest.py`:

```python
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from stockpicker.db.store import Store
from stockpicker.engine.ingester import Ingester


def test_ingester_ingests_prices(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    mock_source = MagicMock()
    mock_source.fetch_prices.return_value = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03"],
        "open": [150.0, 151.0],
        "high": [155.0, 156.0],
        "low": [149.0, 150.0],
        "close": [154.0, 155.0],
        "volume": [1000000, 1100000],
    })
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    result = ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert result["AAPL"]["prices"] == 2
    prices = store.get_prices("AAPL")
    assert len(prices) == 2


def test_ingester_continues_on_source_failure(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    mock_source = MagicMock()
    mock_source.fetch_prices.side_effect = Exception("API down")
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    result = ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    assert result["AAPL"]["prices"] == 0
    assert "error" in result["AAPL"]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_ingest.py -v
```

- [ ] **Step 3: Implement Ingester**

Create `src/stockpicker/engine/ingester.py`:

```python
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.ingester")


class Ingester:
    def __init__(self, store: Store, sources: dict[str, Any]) -> None:
        self.store = store
        self.sources = sources

    def ingest(self, tickers: list[str], start: date, end: date) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for ticker in tickers:
            results[ticker] = self._ingest_ticker(ticker, start, end)
        return results

    def _ingest_ticker(self, ticker: str, start: date, end: date) -> dict:
        result: dict[str, Any] = {"prices": 0, "fundamentals": 0}
        for source_name, source in self.sources.items():
            try:
                prices_df = source.fetch_prices(ticker, start, end)
                if prices_df is not None and not prices_df.empty:
                    self.store.upsert_prices(ticker, prices_df, source=source_name)
                    result["prices"] += len(prices_df)
                    logger.info("Ingested %d price rows for %s from %s", len(prices_df), ticker, source_name)
            except Exception as e:
                logger.error("Failed to fetch prices for %s from %s: %s", ticker, source_name, e)
                result["error"] = str(e)

            try:
                fund_df = source.fetch_fundamentals(ticker)
                if fund_df is not None and not fund_df.empty:
                    self.store.upsert_fundamentals(ticker, fund_df, source=source_name)
                    result["fundamentals"] += len(fund_df)
            except Exception as e:
                logger.error("Failed to fetch fundamentals for %s from %s: %s", ticker, source_name, e)

            try:
                news_df = source.fetch_news(ticker, start, end)
                if news_df is not None and not news_df.empty:
                    logger.info("Ingested %d news rows for %s", len(news_df), ticker)
            except Exception as e:
                logger.error("Failed to fetch news for %s from %s: %s", ticker, source_name, e)

        return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ingest.py -v
```

Expected: PASS

- [ ] **Step 5: Create ingest CLI command**

Create `src/stockpicker/cli/ingest.py`:

```python
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import typer

from stockpicker.db.store import Store
from stockpicker.engine.ingester import Ingester
from stockpicker.sources.yfinance_source import YFinanceSource

ingest_app = typer.Typer(help="Ingest market data from configured sources.")


@ingest_app.command("run")
def ingest_run(
    tickers: list[str] = typer.Argument(..., help="Ticker symbols to ingest"),
    start: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD). Default: 1 year ago."),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Default: today."),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Ingest price and fundamental data for given tickers."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    store = Store(db_path)
    sources = {"yfinance": YFinanceSource()}
    ingester = Ingester(store=store, sources=sources)

    results = ingester.ingest(tickers=tickers, start=start_date, end=end_date)

    for ticker, info in results.items():
        typer.echo(f"{ticker}: {info['prices']} prices, {info['fundamentals']} fundamentals")
        if "error" in info:
            typer.echo(f"  Warning: {info['error']}", err=True)

    store.close()
```

- [ ] **Step 6: Register ingest command in main CLI**

Update `src/stockpicker/cli/main.py`:

```python
import typer

from stockpicker.cli.ingest import ingest_app
from stockpicker.logging_config import setup_logging

app = typer.Typer(
    name="stockpicker",
    help="Stock analysis, scoring, backtesting, and paper trading CLI.",
)


@app.callback()
def main(
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
) -> None:
    """Stockpicker CLI."""
    setup_logging(verbosity=verbose)


app.add_typer(ingest_app, name="ingest")
```

- [ ] **Step 7: Verify CLI**

```bash
uv run stockpicker ingest --help
uv run stockpicker ingest run --help
```

Expected: Help text for ingest subcommands

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add ingest engine and CLI command"
```

---

## Chunk 3: Screening & Scoring

### Task 7: Screening Engine & CLI

**Files:**
- Create: `src/stockpicker/engine/screener.py`
- Create: `src/stockpicker/cli/screen.py`
- Create: `tests/test_screener.py`
- Create: `configs/screens/us-midcap-tech.yaml`

- [ ] **Step 1: Write failing test**

Create `tests/test_screener.py`:

```python
from pathlib import Path

import pandas as pd

from stockpicker.config.models import ScreenConfig
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener


def _seed_db(store: Store) -> None:
    """Seed DB with test tickers having fundamentals."""
    for ticker, pe, mcap, sector, country, vol, price in [
        ("AAPL", 28.0, 3_000_000_000_000, "Technology", "US", 80_000_000, 180.0),
        ("MSFT", 35.0, 2_800_000_000_000, "Technology", "US", 30_000_000, 400.0),
        ("SMALL", 15.0, 500_000_000, "Technology", "US", 200_000, 12.0),
        ("BIGFIN", 12.0, 5_000_000_000, "Financials", "US", 5_000_000, 50.0),
        ("MIDTECH", 20.0, 5_000_000_000, "Technology", "US", 1_000_000, 75.0),
    ]:
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, quarter, pe_ratio) VALUES (?, ?, ?)",
            (ticker, "2024-Q1", pe),
        )
        # Store metadata as a simple ticker_info table
        store._conn.execute(
            "CREATE TABLE IF NOT EXISTS ticker_info "
            "(ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, country TEXT, avg_volume REAL, last_price REAL)"
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO ticker_info VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, mcap, sector, country, vol, price),
        )
    store._conn.commit()


def test_screener_filters_by_market_cap(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_db(store)
    config = ScreenConfig(
        name="Mid Cap",
        filters={"market_cap": [2_000_000_000, 10_000_000_000]},
    )
    screener = Screener(store)
    result = screener.screen(config)
    tickers = result["ticker"].tolist()
    assert "MIDTECH" in tickers
    assert "BIGFIN" in tickers
    assert "AAPL" not in tickers  # too large
    assert "SMALL" not in tickers  # too small


def test_screener_filters_by_sector(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_db(store)
    config = ScreenConfig(
        name="Tech Only",
        filters={"sector": ["Technology"]},
    )
    screener = Screener(store)
    result = screener.screen(config)
    tickers = result["ticker"].tolist()
    assert "BIGFIN" not in tickers
    assert "AAPL" in tickers
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_screener.py -v
```

- [ ] **Step 3: Add ticker_info table migration**

Create `src/stockpicker/db/migrations/002_ticker_info.sql`:

```sql
CREATE TABLE IF NOT EXISTS ticker_info (
    ticker TEXT PRIMARY KEY,
    market_cap REAL,
    sector TEXT,
    country TEXT,
    avg_volume REAL,
    last_price REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Implement Screener**

Create `src/stockpicker/engine/screener.py`:

```python
from __future__ import annotations

import logging

import pandas as pd

from stockpicker.config.models import ScreenConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.screener")

RANGE_FILTERS = {"market_cap", "avg_volume", "last_price", "pe_ratio"}
LIST_FILTERS = {"sector", "country"}
MIN_FILTERS = {"avg_volume_min": "avg_volume", "price_min": "last_price"}


class Screener:
    def __init__(self, store: Store) -> None:
        self.store = store

    def screen(self, config: ScreenConfig) -> pd.DataFrame:
        logger.info("Running screen: %s", config.name)
        df = pd.read_sql_query("SELECT * FROM ticker_info", self.store._conn)
        if df.empty:
            logger.warning("No ticker info in database")
            return df

        for key, value in config.filters.items():
            if key in RANGE_FILTERS and isinstance(value, list) and len(value) == 2:
                low, high = value
                df = df[df[key].between(low, high)]
            elif key in LIST_FILTERS and isinstance(value, list):
                df = df[df[key].isin(value)]
            elif key in MIN_FILTERS:
                col = MIN_FILTERS[key]
                df = df[df[col] >= value]
            else:
                logger.warning("Unknown filter: %s", key)

        logger.info("Screen '%s' returned %d tickers", config.name, len(df))
        return df.reset_index(drop=True)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_screener.py -v
```

Expected: PASS

- [ ] **Step 6: Create screen CLI**

Create `src/stockpicker/cli/screen.py`:

```python
from pathlib import Path

import typer

from stockpicker.config.loader import load_screen
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener

screen_app = typer.Typer(help="Screen stocks by criteria.")


@screen_app.command("run")
def screen_run(
    config: Path = typer.Option(..., "--config", "-c", help="Path to screen YAML config"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Filter stock universe by screening criteria."""
    screen_config = load_screen(config)
    store = Store(db_path)
    screener = Screener(store)
    result = screener.screen(screen_config)

    typer.echo(f"\nScreen: {screen_config.name}")
    typer.echo(f"Results: {len(result)} tickers\n")
    if not result.empty:
        typer.echo(result[["ticker", "market_cap", "sector", "last_price"]].to_string(index=False))

    store.close()
```

- [ ] **Step 7: Register in main CLI**

Update `src/stockpicker/cli/main.py` to add:

```python
from stockpicker.cli.screen import screen_app
app.add_typer(screen_app, name="screen")
```

- [ ] **Step 8: Create example screen config**

Create `configs/screens/us-midcap-tech.yaml`:

```yaml
name: US Mid-Cap Tech
filters:
  market_cap: [2000000000, 10000000000]
  sector: [Technology]
  country: US
  avg_volume_min: 500000
  price_min: 5.0
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: add screening engine and CLI with configurable filters"
```

---

### Task 8: Scoring Engine & CLI

**Files:**
- Create: `src/stockpicker/engine/scorer.py`
- Create: `src/stockpicker/factors/builtin.py`
- Create: `src/stockpicker/cli/score.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_scorer.py`:

```python
from pathlib import Path
import numpy as np
import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer


def _seed_scoring_db(store: Store) -> None:
    for ticker, pe, roe, ret_90d in [
        ("AAPL", 28.0, 0.40, 0.15),
        ("MSFT", 35.0, 0.35, 0.10),
        ("GOOG", 22.0, 0.25, 0.20),
        ("META", 18.0, 0.20, 0.25),
    ]:
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", pe, roe),
        )
        # Add price return data
        store._conn.execute(
            "CREATE TABLE IF NOT EXISTS computed_metrics "
            "(ticker TEXT PRIMARY KEY, price_return_90d REAL, revenue_growth_yoy REAL, news_sentiment_30d REAL)"
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics VALUES (?, ?, ?, ?)",
            (ticker, ret_90d, 0.15, 0.5),
        )
    store._conn.commit()


def test_scorer_produces_ranked_output(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_scoring_db(store)
    model = ModelConfig(
        name="test-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
            FactorConfig(name="momentum", metric="price_return_90d", weight=0.5, direction="higher_is_better"),
        ],
    )
    tickers = ["AAPL", "MSFT", "GOOG", "META"]
    scorer = Scorer(store)
    result = scorer.score(tickers=tickers, model=model)
    assert len(result) == 4
    assert "composite_score" in result.columns
    assert "ticker" in result.columns
    # META should rank high: low PE + high momentum
    assert result.iloc[0]["ticker"] == "META"


def test_scorer_handles_missing_data(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_scoring_db(store)
    model = ModelConfig(
        name="test-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
            FactorConfig(name="sentiment", metric="news_sentiment_30d", weight=0.5, direction="higher_is_better"),
        ],
    )
    # Include a ticker not in DB
    scorer = Scorer(store)
    result = scorer.score(tickers=["AAPL", "UNKNOWN"], model=model)
    # UNKNOWN should be dropped, AAPL should remain
    assert "AAPL" in result["ticker"].values
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_scorer.py -v
```

- [ ] **Step 3: Implement built-in factor metrics**

Create `src/stockpicker/factors/builtin.py`:

```python
"""Maps metric names to (table, column) pairs for data retrieval."""

METRIC_SOURCES: dict[str, tuple[str, str]] = {
    "pe_ratio": ("fundamentals", "pe_ratio"),
    "eps": ("fundamentals", "eps"),
    "revenue": ("fundamentals", "revenue"),
    "gross_margin": ("fundamentals", "gross_margin"),
    "operating_margin": ("fundamentals", "operating_margin"),
    "roe": ("fundamentals", "roe"),
    "return_on_equity": ("fundamentals", "roe"),
    "debt_to_equity": ("fundamentals", "debt_to_equity"),
    "free_cash_flow": ("fundamentals", "free_cash_flow"),
    "revenue_growth_yoy": ("computed_metrics", "revenue_growth_yoy"),
    "price_return_90d": ("computed_metrics", "price_return_90d"),
    "news_sentiment_30d": ("computed_metrics", "news_sentiment_30d"),
}
```

- [ ] **Step 4: Implement Scorer**

Create `src/stockpicker/engine/scorer.py`:

```python
from __future__ import annotations

import importlib
import logging
import uuid

import numpy as np
import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.factors.builtin import METRIC_SOURCES

logger = logging.getLogger("stockpicker.engine.scorer")


class Scorer:
    def __init__(self, store: Store) -> None:
        self.store = store

    def score(self, tickers: list[str], model: ModelConfig) -> pd.DataFrame:
        run_id = str(uuid.uuid4())[:8]
        logger.info("Scoring %d tickers with model '%s' (run %s)", len(tickers), model.name, run_id)

        factor_data: dict[str, pd.Series] = {}
        active_factors: list[FactorConfig] = []

        for factor in model.factors:
            try:
                values = self._get_factor_values(tickers, factor)
                if values is not None and not values.empty:
                    factor_data[factor.name] = values
                    active_factors.append(factor)
                else:
                    logger.warning("No data for factor '%s', skipping", factor.name)
            except Exception as e:
                logger.error("Error computing factor '%s': %s", factor.name, e)

        if not active_factors:
            logger.error("No factors could be computed")
            return pd.DataFrame(columns=["ticker", "composite_score"])

        # Normalize weights for active factors
        total_weight = sum(f.weight for f in active_factors)
        weights = {f.name: f.weight / total_weight for f in active_factors}

        # Build score DataFrame
        all_tickers = set()
        for s in factor_data.values():
            all_tickers.update(s.index)

        records = []
        for ticker in all_tickers:
            composite = 0.0
            factor_scores = {}
            valid = True
            for factor in active_factors:
                if ticker not in factor_data[factor.name].index:
                    valid = False
                    break
                raw = factor_data[factor.name][ticker]
                if pd.isna(raw):
                    valid = False
                    break
                # Normalize: percentile rank
                series = factor_data[factor.name].dropna()
                rank = series.rank(pct=True)
                normalized = rank.get(ticker, np.nan)
                if factor.direction == "lower_is_better":
                    normalized = 1.0 - normalized
                factor_scores[factor.name] = normalized
                composite += normalized * weights[factor.name]

            if valid:
                records.append({"ticker": ticker, "composite_score": composite, **factor_scores})

        result = pd.DataFrame(records)
        if result.empty:
            return pd.DataFrame(columns=["ticker", "composite_score"])

        result = result.sort_values("composite_score", ascending=False).reset_index(drop=True)

        # Save signals to DB
        signal_records = []
        for _, row in result.iterrows():
            for factor in active_factors:
                signal_records.append({
                    "ticker": row["ticker"],
                    "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "model_id": model.name,
                    "run_id": run_id,
                    "factor_name": factor.name,
                    "raw_value": factor_data[factor.name].get(row["ticker"]),
                    "normalized_value": row.get(factor.name),
                    "composite_score": row["composite_score"],
                })
        self.store.save_signals(signal_records)

        return result

    def _get_factor_values(self, tickers: list[str], factor: FactorConfig) -> pd.Series | None:
        if factor.type == "python" and factor.module:
            return self._get_custom_factor(tickers, factor)

        if factor.metric is None:
            return None

        if factor.metric not in METRIC_SOURCES:
            logger.warning("Unknown metric: %s", factor.metric)
            return None

        table, column = METRIC_SOURCES[factor.metric]
        placeholders = ",".join("?" for _ in tickers)
        query = f"SELECT ticker, {column} FROM {table} WHERE ticker IN ({placeholders})"

        # For fundamentals, get most recent quarter
        if table == "fundamentals":
            query = (
                f"SELECT ticker, {column} FROM {table} "
                f"WHERE ticker IN ({placeholders}) "
                f"GROUP BY ticker HAVING quarter = MAX(quarter)"
            )

        df = pd.read_sql_query(query, self.store._conn, params=tickers)
        if df.empty:
            return None
        return df.set_index("ticker")[column]

    def _get_custom_factor(self, tickers: list[str], factor: FactorConfig) -> pd.Series | None:
        try:
            mod = importlib.import_module(factor.module)
            compute_fn = getattr(mod, "compute")
            results = {}
            for ticker in tickers:
                prices = self.store.get_prices(ticker)
                try:
                    results[ticker] = compute_fn(ticker, prices)
                except Exception as e:
                    logger.error("Custom factor '%s' failed for %s: %s", factor.name, ticker, e)
            return pd.Series(results) if results else None
        except Exception as e:
            logger.error("Failed to load custom factor module '%s': %s", factor.module, e)
            return None
```

- [ ] **Step 5: Add computed_metrics migration**

Create `src/stockpicker/db/migrations/003_computed_metrics.sql`:

```sql
CREATE TABLE IF NOT EXISTS computed_metrics (
    ticker TEXT PRIMARY KEY,
    price_return_90d REAL,
    revenue_growth_yoy REAL,
    news_sentiment_30d REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_scorer.py -v
```

Expected: PASS

- [ ] **Step 7: Create score CLI**

Create `src/stockpicker/cli/score.py`:

```python
from pathlib import Path

import typer

from stockpicker.config.loader import load_model, load_screen
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.screener import Screener

score_app = typer.Typer(help="Score stocks using factor models.")


@score_app.command("run")
def score_run(
    screen: str = typer.Option(..., "--screen", "-s", help="Screen config name or path"),
    model: str = typer.Option(..., "--model", "-m", help="Model config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
    top_n: int = typer.Option(20, "--top", "-n", help="Show top N results"),
) -> None:
    """Score screened stocks with a factor model."""
    screen_path = Path(f"configs/screens/{screen}.yaml") if not Path(screen).exists() else Path(screen)
    model_path = Path(f"configs/models/{model}.yaml") if not Path(model).exists() else Path(model)

    screen_config = load_screen(screen_path)
    model_config = load_model(model_path)

    store = Store(db_path)
    screener = Screener(store)
    screened = screener.screen(screen_config)

    if screened.empty:
        typer.echo("No tickers passed screening.")
        raise typer.Exit(1)

    tickers = screened["ticker"].tolist()
    scorer = Scorer(store)
    result = scorer.score(tickers=tickers, model=model_config)

    typer.echo(f"\nModel: {model_config.name}")
    typer.echo(f"Scored: {len(result)} tickers\n")
    if not result.empty:
        typer.echo(result.head(top_n).to_string(index=False))

    store.close()
```

- [ ] **Step 8: Register in main CLI**

Add to `src/stockpicker/cli/main.py`:

```python
from stockpicker.cli.score import score_app
app.add_typer(score_app, name="score")
```

- [ ] **Step 9: Create example model config**

Create `configs/models/multi-factor-v1.yaml`:

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

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add multi-factor scoring engine and CLI"
```

---

## Chunk 4: Backtesting

### Task 9: Backtesting Engine & CLI

**Files:**
- Create: `src/stockpicker/engine/backtester.py`
- Create: `src/stockpicker/cli/backtest.py`
- Create: `tests/test_backtester.py`
- Create: `configs/strategies/momentum-value.yaml`

- [ ] **Step 1: Write failing test**

Create `tests/test_backtester.py`:

```python
from pathlib import Path

import pandas as pd
import numpy as np

from stockpicker.config.models import (
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.backtester import Backtester


def _seed_backtest_db(store: Store) -> None:
    """Create 60 days of price data for 3 tickers."""
    dates = pd.bdate_range("2024-01-02", periods=60)
    for ticker, base_price in [("AAA", 100.0), ("BBB", 50.0), ("CCC", 200.0)]:
        np.random.seed(hash(ticker) % 2**31)
        prices = base_price * (1 + np.random.normal(0.001, 0.02, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": [1000000] * len(dates),
        })
        store.upsert_prices(ticker, df, source="test")


def test_backtester_runs_and_returns_metrics(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_backtest_db(store)

    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=10, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(name="test-strat", screen="test", model="test", rules=rules)

    backtester = Backtester(store)
    # Provide pre-scored rankings per date
    rankings = {}
    dates = pd.bdate_range("2024-01-02", periods=60)
    for d in dates:
        rankings[d.strftime("%Y-%m-%d")] = ["AAA", "BBB", "CCC"]

    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-03-25")

    assert "total_return" in result.metrics
    assert "sharpe_ratio" in result.metrics
    assert "max_drawdown" in result.metrics
    assert len(result.trades) > 0


def test_backtester_applies_stop_loss(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    # Create a ticker that drops 15% immediately
    dates = pd.bdate_range("2024-01-02", periods=20)
    prices = [100.0] + [84.0] * 19  # 16% drop
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "open": prices, "high": prices, "low": prices, "close": prices,
        "volume": [1000000] * len(dates),
    })
    store.upsert_prices("DROP", df, source="test")

    rules = StrategyRules(
        buy=BuyRules(top_n=1, position_size="equal"),
        sell=SellRules(hold_days=30, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=1, max_position_pct=1.0),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=0),
    )
    config = StrategyConfig(name="test-stop", screen="test", model="test", rules=rules)
    rankings = {d.strftime("%Y-%m-%d"): ["DROP"] for d in dates}

    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-01-31")

    sell_trades = [t for t in result.trades if t["action"] == "SELL"]
    assert len(sell_trades) >= 1  # stop loss should trigger
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_backtester.py -v
```

- [ ] **Step 3: Implement Backtester**

Create `src/stockpicker/engine/backtester.py`:

```python
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from stockpicker.config.models import StrategyConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.backtester")


@dataclass
class BacktestResult:
    metrics: dict[str, float]
    trades: list[dict[str, Any]]
    equity_curve: pd.DataFrame


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: float
    days_held: int = 0


class Backtester:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(
        self,
        config: StrategyConfig,
        rankings: dict[str, list[str]],
        start: str,
        end: str,
    ) -> BacktestResult:
        session_id = str(uuid.uuid4())[:8]
        rules = config.rules
        cash = rules.portfolio.initial_capital
        positions: dict[str, Position] = {}
        trades: list[dict] = []
        equity_history: list[dict] = []

        # Get all trading dates
        all_dates = sorted(rankings.keys())
        trading_dates = [d for d in all_dates if start <= d <= end]

        # Cache price data
        all_tickers = set()
        for ranked in rankings.values():
            all_tickers.update(ranked)
        price_cache: dict[str, pd.DataFrame] = {}
        for ticker in all_tickers:
            price_cache[ticker] = self.store.get_prices(ticker, start=start, end=end)

        def get_price(ticker: str, date: str) -> float | None:
            df = price_cache.get(ticker)
            if df is None or df.empty:
                return None
            row = df[df["date"] == date]
            if row.empty:
                return None
            return float(row.iloc[0]["close"])

        for date in trading_dates:
            # Update days held
            for pos in positions.values():
                pos.days_held += 1

            # Check stop losses and hold period exits
            to_sell = []
            for ticker, pos in positions.items():
                current_price = get_price(ticker, date)
                if current_price is None:
                    # Delisted or gap — force exit at last known price
                    to_sell.append((ticker, pos.entry_price, "DELISTED"))
                    continue
                pnl_pct = (current_price - pos.entry_price) / pos.entry_price
                if pnl_pct <= rules.sell.stop_loss:
                    to_sell.append((ticker, current_price, "STOP_LOSS"))
                elif pos.days_held >= rules.sell.hold_days:
                    to_sell.append((ticker, current_price, "HOLD_EXPIRY"))

            for ticker, sell_price, reason in to_sell:
                pos = positions.pop(ticker)
                slippage = sell_price * (rules.costs.slippage_bps / 10000)
                adj_price = sell_price - slippage
                proceeds = adj_price * pos.shares
                cash += proceeds
                trade = {
                    "strategy_id": config.name,
                    "session_type": "backtest",
                    "session_id": session_id,
                    "ticker": ticker,
                    "action": "SELL",
                    "date": date,
                    "price": adj_price,
                    "shares": pos.shares,
                    "commission": rules.costs.commission_per_trade,
                    "slippage": slippage * pos.shares,
                }
                trades.append(trade)
                cash -= rules.costs.commission_per_trade

            # Buy if we have open slots
            ranked = rankings.get(date, [])
            open_slots = rules.portfolio.max_positions - len(positions)
            candidates = [t for t in ranked if t not in positions][:rules.buy.top_n]

            for ticker in candidates[:open_slots]:
                price = get_price(ticker, date)
                if price is None:
                    continue
                slippage = price * (rules.costs.slippage_bps / 10000)
                adj_price = price + slippage
                max_by_pct = rules.portfolio.initial_capital * rules.portfolio.max_position_pct
                position_value = min(cash / max(open_slots, 1), max_by_pct)
                if position_value < adj_price:
                    continue
                shares = position_value / adj_price
                cost = adj_price * shares + rules.costs.commission_per_trade
                if cost > cash:
                    continue
                cash -= cost
                positions[ticker] = Position(
                    ticker=ticker, entry_date=date, entry_price=adj_price, shares=shares
                )
                trades.append({
                    "strategy_id": config.name,
                    "session_type": "backtest",
                    "session_id": session_id,
                    "ticker": ticker,
                    "action": "BUY",
                    "date": date,
                    "price": adj_price,
                    "shares": shares,
                    "commission": rules.costs.commission_per_trade,
                    "slippage": slippage * shares,
                })
                open_slots -= 1

            # Calculate portfolio value
            portfolio_value = cash
            for ticker, pos in positions.items():
                p = get_price(ticker, date)
                if p is not None:
                    portfolio_value += p * pos.shares

            equity_history.append({"date": date, "equity": portfolio_value, "cash": cash})

        # Compute metrics
        equity_df = pd.DataFrame(equity_history)
        metrics = self._compute_metrics(equity_df, rules.portfolio.initial_capital)

        # Save trades to DB
        for t in trades:
            self.store.save_trade(t)

        return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity_df)

    def _compute_metrics(self, equity_df: pd.DataFrame, initial_capital: float) -> dict[str, float]:
        if equity_df.empty:
            return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

        equity = equity_df["equity"].values
        total_return = (equity[-1] - initial_capital) / initial_capital

        # Daily returns
        returns = np.diff(equity) / equity[:-1]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0
        sortino_denom = np.std(returns[returns < 0]) if np.any(returns < 0) else 1e-10
        sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Win rate from trades
        n_days = len(equity_df)
        annualized = (1 + total_return) ** (252 / max(n_days, 1)) - 1 if n_days > 0 else 0.0

        return {
            "total_return": round(total_return, 6),
            "annualized_return": round(annualized, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_drawdown, 6),
            "trading_days": n_days,
        }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_backtester.py -v
```

Expected: PASS

- [ ] **Step 5: Create backtest CLI**

Create `src/stockpicker/cli/backtest.py`:

```python
from pathlib import Path
from typing import Optional

import typer

from stockpicker.config.loader import load_model, load_screen, load_strategy
from stockpicker.db.store import Store
from stockpicker.engine.backtester import Backtester
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.screener import Screener

backtest_app = typer.Typer(help="Backtest trading strategies.")


@backtest_app.command("run")
def backtest_run(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    start: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Run a backtest for a trading strategy."""
    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)

    store = Store(db_path)

    # Load screen and model
    screen_path = Path(f"configs/screens/{config.screen}.yaml")
    model_path = Path(f"configs/models/{config.model}.yaml")
    screen_config = load_screen(screen_path)
    model_config = load_model(model_path)

    # Screen tickers
    screener = Screener(store)
    screened = screener.screen(screen_config)
    if screened.empty:
        typer.echo("No tickers passed screening.")
        raise typer.Exit(1)

    tickers = screened["ticker"].tolist()

    # Score to build rankings (use same ranking for all dates in simple mode)
    scorer = Scorer(store)
    scored = scorer.score(tickers=tickers, model=model_config)
    if scored.empty:
        typer.echo("Scoring produced no results.")
        raise typer.Exit(1)

    ranked_tickers = scored["ticker"].tolist()

    # Build rankings dict — same ranking for all trading days
    import pandas as pd
    trading_dates = pd.bdate_range(start, end)
    rankings = {d.strftime("%Y-%m-%d"): ranked_tickers for d in trading_dates}

    # Run backtest
    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start=start, end=end)

    # Print results
    typer.echo(f"\n{'='*50}")
    typer.echo(f"Backtest: {config.name}")
    typer.echo(f"Period: {start} to {end}")
    typer.echo(f"{'='*50}\n")

    for key, value in result.metrics.items():
        if "return" in key or "drawdown" in key:
            typer.echo(f"  {key}: {value:.2%}")
        else:
            typer.echo(f"  {key}: {value}")

    typer.echo(f"\n  Total trades: {len(result.trades)}")
    store.close()
```

- [ ] **Step 6: Register in main CLI**

Add to `src/stockpicker/cli/main.py`:

```python
from stockpicker.cli.backtest import backtest_app
app.add_typer(backtest_app, name="backtest")
```

- [ ] **Step 7: Create example strategy config**

Create `configs/strategies/momentum-value.yaml`:

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

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add backtesting engine and CLI with stop loss, slippage, and metrics"
```

---

## Chunk 5: Paper Trading & Reporting

### Task 10: Paper Trading Engine & CLI

**Files:**
- Create: `src/stockpicker/engine/paper_trader.py`
- Create: `src/stockpicker/cli/paper.py`
- Create: `tests/test_paper_trader.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_paper_trader.py`:

```python
from pathlib import Path

import pandas as pd

from stockpicker.config.models import (
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.paper_trader import PaperTrader


def _create_paper_session_table(store: Store) -> None:
    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS paper_sessions "
        "(session_id TEXT PRIMARY KEY, strategy_id TEXT, status TEXT, "
        "cash REAL, created_at TEXT DEFAULT (datetime('now')))"
    )
    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS paper_positions "
        "(session_id TEXT, ticker TEXT, shares REAL, entry_price REAL, entry_date TEXT, "
        "PRIMARY KEY (session_id, ticker))"
    )
    store._conn.commit()


def test_paper_trader_start_creates_session(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _create_paper_session_table(store)
    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=10, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(),
    )
    config = StrategyConfig(name="test", screen="test", model="test", rules=rules)
    trader = PaperTrader(store)
    session_id = trader.start(config)
    assert session_id is not None

    cursor = store._conn.execute("SELECT * FROM paper_sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["status"] == "active"
    assert row["cash"] == 100000


def test_paper_trader_status(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _create_paper_session_table(store)
    rules = StrategyRules(
        portfolio=PortfolioRules(initial_capital=50000),
        costs=CostRules(),
    )
    config = StrategyConfig(name="test", screen="test", model="test", rules=rules)
    trader = PaperTrader(store)
    session_id = trader.start(config)
    status = trader.status(session_id)
    assert status["cash"] == 50000
    assert status["positions"] == []
    assert status["status"] == "active"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_paper_trader.py -v
```

- [ ] **Step 3: Add paper trading migration**

Create `src/stockpicker/db/migrations/004_paper_trading.sql`:

```sql
CREATE TABLE IF NOT EXISTS paper_sessions (
    session_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    cash REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS paper_positions (
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    shares REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_date TEXT NOT NULL,
    PRIMARY KEY (session_id, ticker)
);
```

- [ ] **Step 4: Implement PaperTrader**

Create `src/stockpicker/engine/paper_trader.py`:

```python
from __future__ import annotations

import logging
import uuid
from typing import Any

from stockpicker.config.models import StrategyConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.paper_trader")


class PaperTrader:
    def __init__(self, store: Store) -> None:
        self.store = store

    def start(self, config: StrategyConfig) -> str:
        session_id = str(uuid.uuid4())[:8]
        cash = config.rules.portfolio.initial_capital
        self.store._conn.execute(
            "INSERT INTO paper_sessions (session_id, strategy_id, status, cash) VALUES (?, ?, ?, ?)",
            (session_id, config.name, "active", cash),
        )
        self.store._conn.commit()
        logger.info("Started paper session %s for strategy %s", session_id, config.name)
        return session_id

    def status(self, session_id: str) -> dict[str, Any]:
        cursor = self.store._conn.execute(
            "SELECT * FROM paper_sessions WHERE session_id = ?", (session_id,)
        )
        session = cursor.fetchone()
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        positions_cursor = self.store._conn.execute(
            "SELECT * FROM paper_positions WHERE session_id = ?", (session_id,)
        )
        positions = [dict(row) for row in positions_cursor.fetchall()]

        return {
            "session_id": session["session_id"],
            "strategy_id": session["strategy_id"],
            "status": session["status"],
            "cash": session["cash"],
            "positions": positions,
        }

    def run_cycle(self, session_id: str, rankings: list[str], prices: dict[str, float], date: str, config: StrategyConfig) -> dict:
        """Execute one trading cycle for the paper session."""
        status = self.status(session_id)
        if status["status"] != "active":
            return {"error": "Session not active"}

        rules = config.rules
        cash = status["cash"]
        positions = {p["ticker"]: p for p in status["positions"]}
        actions: list[dict] = []

        # Check sells
        for ticker, pos in list(positions.items()):
            current_price = prices.get(ticker)
            if current_price is None:
                continue
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
            days_held = (
                len(list(self.store.get_prices(ticker, start=pos["entry_date"], end=date)))
            )

            should_sell = pnl_pct <= rules.sell.stop_loss or days_held >= rules.sell.hold_days
            if should_sell:
                slippage = current_price * (rules.costs.slippage_bps / 10000)
                adj_price = current_price - slippage
                proceeds = adj_price * pos["shares"] - rules.costs.commission_per_trade
                cash += proceeds
                self.store._conn.execute(
                    "DELETE FROM paper_positions WHERE session_id = ? AND ticker = ?",
                    (session_id, ticker),
                )
                self.store.save_trade({
                    "strategy_id": config.name, "session_type": "paper", "session_id": session_id,
                    "ticker": ticker, "action": "SELL", "date": date,
                    "price": adj_price, "shares": pos["shares"],
                    "commission": rules.costs.commission_per_trade, "slippage": slippage * pos["shares"],
                })
                del positions[ticker]
                actions.append({"action": "SELL", "ticker": ticker, "price": adj_price})

        # Check buys
        open_slots = rules.portfolio.max_positions - len(positions)
        candidates = [t for t in rankings if t not in positions][:rules.buy.top_n]

        for ticker in candidates[:open_slots]:
            price = prices.get(ticker)
            if price is None:
                continue
            slippage = price * (rules.costs.slippage_bps / 10000)
            adj_price = price + slippage
            max_by_pct = rules.portfolio.initial_capital * rules.portfolio.max_position_pct
            position_value = min(cash / max(open_slots, 1), max_by_pct)
            if position_value < adj_price:
                continue
            shares = position_value / adj_price
            cost = adj_price * shares + rules.costs.commission_per_trade
            if cost > cash:
                continue
            cash -= cost
            self.store._conn.execute(
                "INSERT INTO paper_positions (session_id, ticker, shares, entry_price, entry_date) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, ticker, shares, adj_price, date),
            )
            self.store.save_trade({
                "strategy_id": config.name, "session_type": "paper", "session_id": session_id,
                "ticker": ticker, "action": "BUY", "date": date,
                "price": adj_price, "shares": shares,
                "commission": rules.costs.commission_per_trade, "slippage": slippage * shares,
            })
            positions[ticker] = {"ticker": ticker, "shares": shares, "entry_price": adj_price, "entry_date": date}
            open_slots -= 1
            actions.append({"action": "BUY", "ticker": ticker, "price": adj_price})

        # Update cash
        self.store._conn.execute(
            "UPDATE paper_sessions SET cash = ? WHERE session_id = ?", (cash, session_id)
        )
        self.store._conn.commit()

        return {"date": date, "actions": actions, "cash": cash, "positions": len(positions)}

    def stop(self, session_id: str) -> dict:
        self.store._conn.execute(
            "UPDATE paper_sessions SET status = 'stopped' WHERE session_id = ?", (session_id,)
        )
        self.store._conn.commit()
        return self.status(session_id)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_paper_trader.py -v
```

Expected: PASS

- [ ] **Step 6: Create paper CLI**

Create `src/stockpicker/cli/paper.py`:

```python
from pathlib import Path

import typer

from stockpicker.config.loader import load_strategy
from stockpicker.db.store import Store
from stockpicker.engine.paper_trader import PaperTrader

paper_app = typer.Typer(help="Paper trade strategies with simulated capital.")


@paper_app.command("start")
def paper_start(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Start a new paper trading session."""
    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)
    store = Store(db_path)
    trader = PaperTrader(store)
    session_id = trader.start(config)
    typer.echo(f"Paper trading session started: {session_id}")
    typer.echo(f"Strategy: {config.name}")
    typer.echo(f"Initial capital: ${config.rules.portfolio.initial_capital:,.2f}")
    typer.echo(f"\nRun 'stockpicker paper run-cycle --session {session_id}' daily to advance.")
    store.close()


@paper_app.command("status")
def paper_status(
    session: str = typer.Option(..., "--session", help="Session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Show current paper trading status."""
    store = Store(db_path)
    trader = PaperTrader(store)
    status = trader.status(session)
    typer.echo(f"\nSession: {status['session_id']}")
    typer.echo(f"Strategy: {status['strategy_id']}")
    typer.echo(f"Status: {status['status']}")
    typer.echo(f"Cash: ${status['cash']:,.2f}")
    typer.echo(f"Positions: {len(status['positions'])}")
    for pos in status["positions"]:
        typer.echo(f"  {pos['ticker']}: {pos['shares']:.2f} shares @ ${pos['entry_price']:.2f}")
    store.close()


@paper_app.command("run-cycle")
def paper_run_cycle(
    session: str = typer.Option(..., "--session", help="Session ID"),
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Run one paper trading cycle (designed to be called via cron)."""
    from datetime import date as date_cls, timedelta

    from stockpicker.config.loader import load_model, load_screen, load_strategy
    from stockpicker.engine.ingester import Ingester
    from stockpicker.engine.scorer import Scorer
    from stockpicker.engine.screener import Screener
    from stockpicker.sources.yfinance_source import YFinanceSource

    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)
    store = Store(db_path)

    today = date_cls.today()

    # 1. Ingest fresh data
    screen_path = Path(f"configs/screens/{config.screen}.yaml")
    screen_config = load_screen(screen_path)
    screener = Screener(store)
    screened = screener.screen(screen_config)
    tickers = screened["ticker"].tolist() if not screened.empty else []

    sources = {"yfinance": YFinanceSource()}
    ingester = Ingester(store=store, sources=sources)
    ingester.ingest(tickers=tickers, start=today - timedelta(days=7), end=today)

    # 2. Score
    model_path = Path(f"configs/models/{config.model}.yaml")
    model_config = load_model(model_path)
    scorer = Scorer(store)
    scored = scorer.score(tickers=tickers, model=model_config)
    rankings = scored["ticker"].tolist() if not scored.empty else []

    # 3. Get current prices
    prices = {}
    for ticker in tickers:
        p = store.get_prices(ticker, start=today.isoformat(), end=today.isoformat())
        if not p.empty:
            prices[ticker] = float(p.iloc[-1]["close"])

    # 4. Execute cycle
    trader = PaperTrader(store)
    result = trader.run_cycle(session, rankings, prices, today.isoformat(), config)

    typer.echo(f"\nPaper trade cycle: {today}")
    typer.echo(f"  Actions: {len(result.get('actions', []))}")
    for action in result.get("actions", []):
        typer.echo(f"    {action['action']} {action['ticker']} @ ${action['price']:.2f}")
    typer.echo(f"  Cash: ${result.get('cash', 0):,.2f}")
    typer.echo(f"  Positions: {result.get('positions', 0)}")
    store.close()


@paper_app.command("stop")
def paper_stop(
    session: str = typer.Option(..., "--session", help="Session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Stop a paper trading session."""
    store = Store(db_path)
    trader = PaperTrader(store)
    result = trader.stop(session)
    typer.echo(f"Session {session} stopped. Final cash: ${result['cash']:,.2f}")
    store.close()
```

- [ ] **Step 7: Register in main CLI**

Add to `src/stockpicker/cli/main.py`:

```python
from stockpicker.cli.paper import paper_app
app.add_typer(paper_app, name="paper")
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add paper trading engine and CLI with session management"
```

---

### Task 11: Reporting Engine & CLI

**Files:**
- Create: `src/stockpicker/engine/reporter.py`
- Create: `src/stockpicker/cli/report.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_reporter.py`:

```python
import pandas as pd
import numpy as np

from stockpicker.engine.reporter import Reporter


def test_reporter_strategy_report():
    equity_data = {
        "date": pd.bdate_range("2024-01-02", periods=60).strftime("%Y-%m-%d").tolist(),
        "equity": (100000 * (1 + np.random.normal(0.001, 0.01, 60)).cumprod()).tolist(),
    }
    equity_df = pd.DataFrame(equity_data)
    trades = [
        {"ticker": "AAPL", "action": "BUY", "date": "2024-01-02", "price": 150.0, "shares": 100},
        {"ticker": "AAPL", "action": "SELL", "date": "2024-02-01", "price": 160.0, "shares": 100},
    ]

    reporter = Reporter()
    report = reporter.strategy_report(
        name="test", equity_curve=equity_df, trades=trades, initial_capital=100000
    )
    assert "total_return" in report
    assert "sharpe_ratio" in report
    assert "max_drawdown" in report
    assert "win_rate" in report
    assert "total_trades" in report


def test_reporter_compare():
    reporter = Reporter()
    reports = {
        "strat_a": {"total_return": 0.15, "sharpe_ratio": 1.2, "max_drawdown": -0.08},
        "strat_b": {"total_return": 0.10, "sharpe_ratio": 0.9, "max_drawdown": -0.12},
    }
    comparison = reporter.compare(reports)
    assert len(comparison) == 2
    assert "strategy" in comparison.columns
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_reporter.py -v
```

- [ ] **Step 3: Implement Reporter**

Create `src/stockpicker/engine/reporter.py`:

```python
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("stockpicker.engine.reporter")


class Reporter:
    def strategy_report(
        self,
        name: str,
        equity_curve: pd.DataFrame,
        trades: list[dict],
        initial_capital: float,
    ) -> dict[str, Any]:
        equity = equity_curve["equity"].values

        total_return = (equity[-1] - initial_capital) / initial_capital
        n_days = len(equity)
        annualized = (1 + total_return) ** (252 / max(n_days, 1)) - 1

        returns = np.diff(equity) / equity[:-1]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0
        neg_returns = returns[returns < 0]
        sortino_denom = np.std(neg_returns) if len(neg_returns) > 0 else 1e-10
        sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Win rate from trade pairs
        buys = {t["ticker"]: t for t in trades if t["action"] == "BUY"}
        sells = [t for t in trades if t["action"] == "SELL"]
        wins = sum(1 for s in sells if s["ticker"] in buys and s["price"] > buys[s["ticker"]]["price"])
        total_closed = len(sells)
        win_rate = wins / total_closed if total_closed > 0 else 0.0

        return {
            "strategy": name,
            "total_return": round(total_return, 6),
            "annualized_return": round(annualized, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_drawdown, 6),
            "win_rate": round(win_rate, 4),
            "total_trades": len(trades),
            "trading_days": n_days,
        }

    def compare(self, reports: dict[str, dict]) -> pd.DataFrame:
        rows = []
        for name, metrics in reports.items():
            rows.append({"strategy": name, **metrics})
        return pd.DataFrame(rows)

    def format_report(self, report: dict[str, Any]) -> str:
        lines = [
            f"Strategy: {report['strategy']}",
            f"{'='*40}",
            f"  Total Return:      {report['total_return']:.2%}",
            f"  Annualized Return: {report['annualized_return']:.2%}",
            f"  Sharpe Ratio:      {report['sharpe_ratio']:.4f}",
            f"  Sortino Ratio:     {report['sortino_ratio']:.4f}",
            f"  Max Drawdown:      {report['max_drawdown']:.2%}",
            f"  Win Rate:          {report['win_rate']:.2%}",
            f"  Total Trades:      {report['total_trades']}",
            f"  Trading Days:      {report['trading_days']}",
        ]
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_reporter.py -v
```

Expected: PASS

- [ ] **Step 5: Create report CLI**

Create `src/stockpicker/cli/report.py`:

```python
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from stockpicker.db.store import Store
from stockpicker.engine.reporter import Reporter

report_app = typer.Typer(help="Generate performance reports.")


def _reconstruct_equity_curve(store: Store, strategy_id: str, session_id: str | None) -> tuple[pd.DataFrame, list[dict], float]:
    """Rebuild equity curve from trade log. Returns (equity_df, trades, initial_capital)."""
    trades_df = store.get_trades(strategy_id=strategy_id, session_id=session_id)
    if trades_df.empty:
        return pd.DataFrame(), [], 0.0
    trades = trades_df.to_dict("records")

    # Determine initial capital from first buy total
    buys = [t for t in trades if t["action"] == "BUY"]
    if not buys:
        return pd.DataFrame(), trades, 0.0
    # Estimate initial capital: sum of first batch of buys
    first_date = buys[0]["date"]
    first_buys = [b for b in buys if b["date"] == first_date]
    initial_capital = sum(b["price"] * b["shares"] + b.get("commission", 0) for b in first_buys) * 2  # rough estimate

    # Build daily equity from trades and price data
    all_dates = sorted(set(t["date"] for t in trades))
    if len(all_dates) < 2:
        return pd.DataFrame({"date": all_dates, "equity": [initial_capital]}), trades, initial_capital

    # Get price range
    start, end = all_dates[0], all_dates[-1]
    tickers = list(set(t["ticker"] for t in trades))
    all_trading_dates = pd.bdate_range(start, end).strftime("%Y-%m-%d").tolist()

    cash = initial_capital
    positions: dict[str, tuple[float, float]] = {}  # ticker -> (shares, entry_price)
    equity_records = []
    trade_idx = 0

    for date in all_trading_dates:
        while trade_idx < len(trades) and trades[trade_idx]["date"] == date:
            t = trades[trade_idx]
            if t["action"] == "BUY":
                cost = t["price"] * t["shares"] + t.get("commission", 0)
                cash -= cost
                prev = positions.get(t["ticker"], (0.0, 0.0))
                positions[t["ticker"]] = (prev[0] + t["shares"], t["price"])
            elif t["action"] == "SELL":
                proceeds = t["price"] * t["shares"] - t.get("commission", 0)
                cash += proceeds
                if t["ticker"] in positions:
                    remaining = positions[t["ticker"]][0] - t["shares"]
                    if remaining <= 0.01:
                        del positions[t["ticker"]]
                    else:
                        positions[t["ticker"]] = (remaining, positions[t["ticker"]][1])
            trade_idx += 1

        portfolio_value = cash
        for ticker, (shares, _) in positions.items():
            prices = store.get_prices(ticker, start=date, end=date)
            if not prices.empty:
                portfolio_value += float(prices.iloc[0]["close"]) * shares
        equity_records.append({"date": date, "equity": portfolio_value})

    return pd.DataFrame(equity_records), trades, initial_capital


@report_app.command("strategy")
def report_strategy(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy name"),
    session_id: Optional[str] = typer.Option(None, "--session", help="Specific session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Show performance report for a strategy."""
    store = Store(db_path)
    equity_df, trades, initial_capital = _reconstruct_equity_curve(store, strategy, session_id)

    if not trades:
        typer.echo(f"No trades found for strategy '{strategy}'")
        raise typer.Exit(1)

    reporter = Reporter()
    if not equity_df.empty and initial_capital > 0:
        report = reporter.strategy_report(strategy, equity_df, trades, initial_capital)
        typer.echo(reporter.format_report(report))
    else:
        typer.echo(f"\n{strategy}: {len(trades)} trades (insufficient data for full metrics)")

    store.close()


@report_app.command("compare")
def report_compare(
    strategies: str = typer.Option(..., "--compare", help="Comma-separated strategy names"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Compare multiple strategies side by side."""
    store = Store(db_path)
    names = [s.strip() for s in strategies.split(",")]
    reporter = Reporter()
    reports = {}

    for name in names:
        equity_df, trades, initial_capital = _reconstruct_equity_curve(store, name, None)
        if trades and not equity_df.empty and initial_capital > 0:
            reports[name] = reporter.strategy_report(name, equity_df, trades, initial_capital)
        else:
            typer.echo(f"Warning: insufficient data for {name}")

    if reports:
        comparison = reporter.compare(reports)
        typer.echo("\nStrategy Comparison")
        typer.echo("=" * 80)
        typer.echo(comparison.to_string(index=False))

    store.close()
```

- [ ] **Step 6: Register in main CLI**

Add to `src/stockpicker/cli/main.py`:

```python
from stockpicker.cli.report import report_app
app.add_typer(report_app, name="report")
```

- [ ] **Step 7: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add reporting engine and CLI with strategy comparison"
```

---

## Chunk 6: Integration & Final Wiring

### Task 12: Final CLI Wiring

**Files:**
- Modify: `src/stockpicker/cli/main.py`

- [ ] **Step 1: Write final main.py with all subcommands**

```python
import typer

from stockpicker.cli.backtest import backtest_app
from stockpicker.cli.ingest import ingest_app
from stockpicker.cli.paper import paper_app
from stockpicker.cli.report import report_app
from stockpicker.cli.score import score_app
from stockpicker.cli.screen import screen_app
from stockpicker.logging_config import setup_logging

app = typer.Typer(
    name="stockpicker",
    help="Stock analysis, scoring, backtesting, and paper trading CLI.",
)


@app.callback()
def main(
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
) -> None:
    """Stockpicker CLI."""
    setup_logging(verbosity=verbose)


app.add_typer(ingest_app, name="ingest")
app.add_typer(screen_app, name="screen")
app.add_typer(score_app, name="score")
app.add_typer(backtest_app, name="backtest")
app.add_typer(paper_app, name="paper")
app.add_typer(report_app, name="report")
```

- [ ] **Step 2: Verify full CLI**

```bash
uv run stockpicker --help
uv run stockpicker ingest --help
uv run stockpicker screen --help
uv run stockpicker score --help
uv run stockpicker backtest --help
uv run stockpicker paper --help
uv run stockpicker report --help
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: wire all CLI subcommands"
```

---

### Task 13: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
"""End-to-end test: ingest → screen → score → backtest pipeline using fixture data."""
from pathlib import Path

import pandas as pd
import numpy as np

from stockpicker.config.models import (
    ScreenConfig, ModelConfig, FactorConfig,
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.backtester import Backtester


def test_full_pipeline(tmp_path: Path):
    store = Store(tmp_path / "test.db")

    # Seed price data for 5 tickers
    dates = pd.bdate_range("2024-01-02", periods=60)
    tickers_data = {
        "ALPHA": (100.0, 0.002),   # slight uptrend
        "BETA": (50.0, -0.001),    # slight downtrend
        "GAMMA": (200.0, 0.003),   # stronger uptrend
        "DELTA": (75.0, 0.0),      # flat
        "EPSILON": (150.0, 0.001), # mild uptrend
    }

    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS ticker_info "
        "(ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, country TEXT, avg_volume REAL, last_price REAL)"
    )
    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS computed_metrics "
        "(ticker TEXT PRIMARY KEY, price_return_90d REAL, revenue_growth_yoy REAL, news_sentiment_30d REAL)"
    )

    for ticker, (base, drift) in tickers_data.items():
        np.random.seed(hash(ticker) % 2**31)
        prices = base * (1 + np.random.normal(drift, 0.015, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": [1000000] * len(dates),
        })
        store.upsert_prices(ticker, df, source="test")

        ret_90d = (prices[-1] - prices[0]) / prices[0]
        store._conn.execute(
            "INSERT INTO ticker_info VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, 5_000_000_000, "Technology", "US", 1_000_000, float(prices[-1])),
        )
        store._conn.execute(
            "INSERT INTO fundamentals (ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", 20.0 + np.random.uniform(-5, 10), np.random.uniform(0.1, 0.3)),
        )
        store._conn.execute(
            "INSERT INTO computed_metrics VALUES (?, ?, ?, ?)",
            (ticker, float(ret_90d), 0.15, 0.5),
        )
    store._conn.commit()

    # Screen
    screen_config = ScreenConfig(name="All Tech", filters={"sector": ["Technology"]})
    screener = Screener(store)
    screened = screener.screen(screen_config)
    assert len(screened) == 5

    # Score
    model = ModelConfig(name="test-model", factors=[
        FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
        FactorConfig(name="momentum", metric="price_return_90d", weight=0.5, direction="higher_is_better"),
    ])
    scorer = Scorer(store)
    scored = scorer.score(tickers=screened["ticker"].tolist(), model=model)
    assert len(scored) == 5

    # Backtest
    rules = StrategyRules(
        buy=BuyRules(top_n=3, position_size="equal"),
        sell=SellRules(hold_days=20, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=100000, max_positions=3, max_position_pct=0.4),
        costs=CostRules(commission_per_trade=0.0, slippage_bps=5),
    )
    config = StrategyConfig(name="integration-test", screen="test", model="test-model", rules=rules)
    ranked = scored["ticker"].tolist()
    rankings = {d.strftime("%Y-%m-%d"): ranked for d in dates}

    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-03-25")

    assert result.metrics["trading_days"] > 0
    assert len(result.trades) > 0
    assert "total_return" in result.metrics
    assert "sharpe_ratio" in result.metrics

    store.close()
```

- [ ] **Step 2: Run integration test**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: PASS

- [ ] **Step 3: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: add end-to-end integration test for full pipeline"
```

---

## Chunk 7: Derived Data, Additional Sources & Factor Evaluation

### Task 14: Computed Metrics & Ticker Info Population

**Files:**
- Create: `src/stockpicker/engine/metrics_computer.py`
- Modify: `src/stockpicker/engine/ingester.py`
- Create: `tests/test_metrics_computer.py`

The screener needs `ticker_info` and the scorer needs `computed_metrics`. These must be populated from raw ingested data.

- [ ] **Step 1: Write failing test**

Create `tests/test_metrics_computer.py`:

```python
from pathlib import Path

import pandas as pd
import numpy as np

from stockpicker.db.store import Store
from stockpicker.engine.metrics_computer import MetricsComputer


def _seed_raw_data(store: Store) -> None:
    dates = pd.bdate_range("2024-01-02", periods=90)
    for ticker, base, drift in [("AAPL", 150.0, 0.002), ("MSFT", 350.0, -0.001)]:
        np.random.seed(hash(ticker) % 2**31)
        prices = base * (1 + np.random.normal(drift, 0.015, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": [1000000 + i * 1000 for i in range(len(dates))],
        })
        store.upsert_prices(ticker, df, source="test")
        store.upsert_fundamentals(ticker, pd.DataFrame({
            "quarter": ["2024-Q1"],
            "eps": [5.0], "pe_ratio": [28.0], "revenue": [1e10],
            "gross_margin": [0.4], "operating_margin": [0.3], "roe": [0.25],
            "debt_to_equity": [1.5], "free_cash_flow": [5e9],
        }), source="test")


def test_compute_ticker_info(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_raw_data(store)
    computer = MetricsComputer(store)
    computer.compute_all(["AAPL", "MSFT"])

    df = pd.read_sql_query("SELECT * FROM ticker_info", store._conn)
    assert len(df) == 2
    assert all(col in df.columns for col in ["ticker", "market_cap", "avg_volume", "last_price"])


def test_compute_metrics(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    _seed_raw_data(store)
    computer = MetricsComputer(store)
    computer.compute_all(["AAPL", "MSFT"])

    df = pd.read_sql_query("SELECT * FROM computed_metrics", store._conn)
    assert len(df) == 2
    assert "price_return_90d" in df.columns
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_metrics_computer.py -v
```

- [ ] **Step 3: Implement MetricsComputer**

Create `src/stockpicker/engine/metrics_computer.py`:

```python
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.metrics_computer")


class MetricsComputer:
    def __init__(self, store: Store) -> None:
        self.store = store

    def compute_all(self, tickers: list[str]) -> None:
        for ticker in tickers:
            try:
                self._compute_ticker_info(ticker)
                self._compute_derived_metrics(ticker)
            except Exception as e:
                logger.error("Failed to compute metrics for %s: %s", ticker, e)

    def _compute_ticker_info(self, ticker: str) -> None:
        prices = self.store.get_prices(ticker)
        if prices.empty:
            return
        fund = self.store.get_fundamentals(ticker)

        last_price = float(prices.iloc[-1]["close"])
        avg_volume = float(prices["volume"].tail(30).mean())

        # Estimate market cap from PE and EPS if available
        market_cap = None
        if not fund.empty:
            pe = fund.iloc[-1].get("pe_ratio")
            eps = fund.iloc[-1].get("eps")
            if pe and eps and pe > 0 and eps > 0:
                market_cap = last_price / eps * eps * pe * 1e6  # rough estimate

        # Get sector/country from fundamentals or default
        sector = "Unknown"
        country = "US"

        self.store._conn.execute(
            "INSERT OR REPLACE INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, market_cap, sector, country, avg_volume, last_price),
        )
        self.store._conn.commit()

    def _compute_derived_metrics(self, ticker: str) -> None:
        prices = self.store.get_prices(ticker)
        if len(prices) < 2:
            return

        closes = prices["close"].values.astype(float)

        # 90-day price return (or max available)
        lookback = min(90, len(closes))
        price_return_90d = (closes[-1] - closes[-lookback]) / closes[-lookback]

        # Revenue growth YoY (placeholder — needs multiple quarters)
        fund = self.store.get_fundamentals(ticker)
        revenue_growth_yoy = None
        if len(fund) >= 2:
            rev_recent = fund.iloc[-1].get("revenue")
            rev_prior = fund.iloc[-2].get("revenue")
            if rev_recent and rev_prior and rev_prior > 0:
                revenue_growth_yoy = (rev_recent - rev_prior) / rev_prior

        self.store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
            "VALUES (?, ?, ?, ?)",
            (ticker, price_return_90d, revenue_growth_yoy, None),
        )
        self.store._conn.commit()
```

- [ ] **Step 4: Wire MetricsComputer into ingest CLI**

Update `src/stockpicker/cli/ingest.py` to add after ingestion:

```python
from stockpicker.engine.metrics_computer import MetricsComputer

# After ingestion loop, add:
    computer = MetricsComputer(store)
    computer.compute_all(tickers)
    typer.echo("Computed derived metrics.")
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_metrics_computer.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add MetricsComputer to populate ticker_info and computed_metrics from raw data"
```

---

### Task 15: FRED & EDGAR Source Stubs

**Files:**
- Create: `src/stockpicker/sources/fred_source.py`
- Create: `src/stockpicker/sources/edgar_source.py`
- Create: `tests/test_fred_source.py`
- Create: `tests/test_edgar_source.py`

These are stub implementations that establish the adapter pattern. Full implementation can be filled in iteratively.

- [ ] **Step 1: Write tests**

Create `tests/test_fred_source.py`:

```python
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
```

Create `tests/test_edgar_source.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_fred_source.py tests/test_edgar_source.py -v
```

- [ ] **Step 3: Implement FRED stub**

Create `src/stockpicker/sources/fred_source.py`:

```python
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger("stockpicker.sources.fred")


class FredSource:
    """FRED data source stub. TODO: implement with fredapi or direct API calls."""

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        logger.warning("FRED source not yet implemented — returning empty")
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None
```

- [ ] **Step 4: Implement EDGAR stub**

Create `src/stockpicker/sources/edgar_source.py`:

```python
from __future__ import annotations

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger("stockpicker.sources.edgar")


class EdgarSource:
    """SEC EDGAR data source stub. TODO: implement with SEC EDGAR API."""

    def fetch_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    def fetch_fundamentals(self, ticker: str) -> pd.DataFrame:
        logger.warning("EDGAR source not yet implemented — returning empty")
        return pd.DataFrame(columns=[
            "quarter", "eps", "pe_ratio", "revenue", "gross_margin",
            "operating_margin", "roe", "debt_to_equity", "free_cash_flow",
        ])

    def fetch_news(self, ticker: str, start: date, end: date) -> pd.DataFrame | None:
        return None
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_fred_source.py tests/test_edgar_source.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add FRED and EDGAR data source stubs"
```

---

### Task 16: Factor Evaluation Report

**Files:**
- Modify: `src/stockpicker/engine/reporter.py`
- Modify: `src/stockpicker/cli/report.py`
- Create: `tests/test_factor_evaluation.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_factor_evaluation.py`:

```python
import pandas as pd
import numpy as np

from stockpicker.engine.reporter import Reporter


def test_factor_evaluation():
    reporter = Reporter()
    signals = pd.DataFrame({
        "ticker": ["A", "A", "B", "B", "C", "C"],
        "factor_name": ["value", "momentum", "value", "momentum", "value", "momentum"],
        "normalized_value": [0.8, 0.3, 0.4, 0.7, 0.6, 0.5],
        "composite_score": [0.55, 0.55, 0.55, 0.55, 0.55, 0.55],
    })
    returns = pd.Series({"A": 0.10, "B": 0.05, "C": -0.02})

    result = reporter.factor_evaluation(signals, returns)
    assert "factor_name" in result.columns
    assert "ic" in result.columns  # information coefficient
    assert len(result) == 2  # two factors
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_factor_evaluation.py -v
```

- [ ] **Step 3: Add factor_evaluation to Reporter**

Add to `src/stockpicker/engine/reporter.py`:

```python
    def factor_evaluation(self, signals: pd.DataFrame, returns: pd.Series) -> pd.DataFrame:
        """Evaluate factor predictiveness via information coefficient."""
        factors = signals["factor_name"].unique()
        records = []
        for factor in factors:
            factor_data = signals[signals["factor_name"] == factor].set_index("ticker")
            common = factor_data.index.intersection(returns.index)
            if len(common) < 3:
                records.append({"factor_name": factor, "ic": None, "avg_score": None})
                continue
            factor_scores = factor_data.loc[common, "normalized_value"]
            factor_returns = returns.loc[common]
            ic = factor_scores.corr(factor_returns)
            records.append({
                "factor_name": factor,
                "ic": round(ic, 4) if not pd.isna(ic) else None,
                "avg_score": round(factor_scores.mean(), 4),
            })
        return pd.DataFrame(records)

    def format_factor_evaluation(self, eval_df: pd.DataFrame) -> str:
        lines = ["Factor Evaluation", "=" * 40]
        for _, row in eval_df.iterrows():
            ic_str = f"{row['ic']:.4f}" if row["ic"] is not None else "N/A"
            lines.append(f"  {row['factor_name']}: IC={ic_str}")
        return "\n".join(lines)
```

- [ ] **Step 4: Add evaluate-factors CLI command**

Add to `src/stockpicker/cli/report.py`:

```python
@report_app.command("evaluate-factors")
def report_evaluate_factors(
    model: str = typer.Option(..., "--model", "-m", help="Model name"),
    period: str = typer.Option("90d", "--period", help="Lookback period (e.g., 90d)"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Evaluate individual factor predictiveness."""
    store = Store(db_path)

    # Get signals for this model
    signals_df = pd.read_sql_query(
        "SELECT * FROM signals WHERE model_id = ? ORDER BY date DESC",
        store._conn, params=[model],
    )
    if signals_df.empty:
        typer.echo(f"No signals found for model '{model}'")
        raise typer.Exit(1)

    # Get price returns for tickers in signals
    tickers = signals_df["ticker"].unique().tolist()
    returns = {}
    for ticker in tickers:
        prices = store.get_prices(ticker)
        if len(prices) >= 2:
            closes = prices["close"].values.astype(float)
            returns[ticker] = (closes[-1] - closes[0]) / closes[0]

    reporter = Reporter()
    eval_result = reporter.factor_evaluation(signals_df, pd.Series(returns))
    typer.echo(reporter.format_factor_evaluation(eval_result))
    store.close()
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_factor_evaluation.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add factor evaluation report with information coefficient"
```

---

### Task 17: Custom Factor Plugin Test

**Files:**
- Create: `tests/fixtures/sample_custom_factor.py`
- Create: `tests/test_custom_factor.py`

- [ ] **Step 1: Create sample custom factor**

Create `tests/fixtures/sample_custom_factor.py`:

```python
"""Sample custom factor for testing the plugin interface."""
import pandas as pd


def compute(ticker: str, data: pd.DataFrame) -> float:
    """Compute a simple momentum score from price data."""
    if data.empty or len(data) < 2:
        return 0.0
    closes = data["close"].values.astype(float)
    return float((closes[-1] - closes[0]) / closes[0])
```

- [ ] **Step 2: Write test**

Create `tests/test_custom_factor.py`:

```python
import sys
from pathlib import Path

import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer


def test_custom_factor_loads_and_scores(tmp_path: Path):
    # Add fixtures dir to path so the custom module can be imported
    fixtures_dir = Path(__file__).parent / "fixtures"
    sys.path.insert(0, str(fixtures_dir))

    store = Store(tmp_path / "test.db")

    # Seed price data
    df = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "open": [100.0, 105.0, 108.0],
        "high": [106.0, 110.0, 112.0],
        "low": [99.0, 104.0, 107.0],
        "close": [105.0, 108.0, 110.0],
        "volume": [1000000, 1100000, 1050000],
    })
    store.upsert_prices("TEST", df, source="test")

    model = ModelConfig(
        name="custom-test",
        factors=[
            FactorConfig(
                name="custom_momentum",
                type="python",
                module="sample_custom_factor",
                weight=1.0,
            ),
        ],
    )

    scorer = Scorer(store)
    result = scorer.score(tickers=["TEST"], model=model)
    assert len(result) == 1
    assert "composite_score" in result.columns

    sys.path.pop(0)
```

- [ ] **Step 3: Run test**

```bash
uv run pytest tests/test_custom_factor.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: add custom factor plugin test with sample fixture"
```

---

### Task 18: Incremental Ingestion

**Files:**
- Modify: `src/stockpicker/engine/ingester.py`
- Modify: `tests/test_ingest.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_ingest.py`:

```python
def test_ingester_incremental_fetches_from_last_date(tmp_path: Path):
    store = Store(tmp_path / "test.db")

    # Pre-seed with data up to Jan 15
    existing = pd.DataFrame({
        "date": ["2024-01-10", "2024-01-11", "2024-01-12", "2024-01-15"],
        "open": [100.0] * 4, "high": [101.0] * 4,
        "low": [99.0] * 4, "close": [100.5] * 4, "volume": [1000000] * 4,
    })
    store.upsert_prices("AAPL", existing, source="test")

    # Mock source that records what date range was requested
    mock_source = MagicMock()
    mock_source.fetch_prices.return_value = pd.DataFrame({
        "date": ["2024-01-16"], "open": [101.0], "high": [102.0],
        "low": [100.0], "close": [101.5], "volume": [1100000],
    })
    mock_source.fetch_fundamentals.return_value = pd.DataFrame()
    mock_source.fetch_news.return_value = None

    ingester = Ingester(store=store, sources={"yfinance": mock_source})
    ingester.ingest(tickers=["AAPL"], start=date(2024, 1, 1), end=date(2024, 1, 31))

    # Verify fetch_prices was called with start=Jan 16 (day after last ingested)
    call_args = mock_source.fetch_prices.call_args
    assert call_args[0][1] == date(2024, 1, 16)  # start should be day after last
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_ingest.py::test_ingester_incremental_fetches_from_last_date -v
```

- [ ] **Step 3: Update Ingester for incremental behavior**

Modify `_ingest_ticker` in `src/stockpicker/engine/ingester.py` to check last ingested date:

```python
    def _ingest_ticker(self, ticker: str, start: date, end: date) -> dict:
        result: dict[str, Any] = {"prices": 0, "fundamentals": 0}

        # Check last ingested date for incremental fetch
        existing = self.store.get_prices(ticker)
        effective_start = start
        if not existing.empty:
            last_date = existing.iloc[-1]["date"]
            from datetime import timedelta
            effective_start = max(start, date.fromisoformat(last_date) + timedelta(days=1))
            if effective_start > end:
                logger.info("Ticker %s already up to date", ticker)
                return result

        for source_name, source in self.sources.items():
            # ... rest of method uses effective_start instead of start for fetch_prices
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ingest.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add incremental ingestion — only fetch data since last run"
```

---

### Task 19: Final Full Test Suite & Cleanup

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All PASS

- [ ] **Step 2: Verify all CLI commands work**

```bash
uv run stockpicker --help
uv run stockpicker ingest --help
uv run stockpicker screen --help
uv run stockpicker score --help
uv run stockpicker backtest --help
uv run stockpicker paper --help
uv run stockpicker paper run-cycle --help
uv run stockpicker report --help
uv run stockpicker report evaluate-factors --help
```

- [ ] **Step 3: Commit any final cleanup**

```bash
git add -A
git commit -m "chore: final cleanup and verify all CLI commands"
```

---

### Task 20: CLI Integration Tests

**Files:**
- Create: `tests/test_cli_integration.py`

Tests that exercise the actual CLI commands via Typer's test runner, verifying that the full stack (CLI → engine → DB) works end-to-end.

- [ ] **Step 1: Write CLI integration tests**

Create `tests/test_cli_integration.py`:

```python
"""CLI integration tests using Typer's CliRunner."""
from pathlib import Path

import numpy as np
import pandas as pd
from typer.testing import CliRunner

from stockpicker.cli.main import app
from stockpicker.db.store import Store

runner = CliRunner()


def _seed_full_db(db_path: Path) -> None:
    """Seed a database with enough data to run the full pipeline."""
    store = Store(db_path)

    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS ticker_info "
        "(ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, country TEXT, avg_volume REAL, last_price REAL)"
    )
    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS computed_metrics "
        "(ticker TEXT PRIMARY KEY, price_return_90d REAL, revenue_growth_yoy REAL, news_sentiment_30d REAL)"
    )

    dates = pd.bdate_range("2024-01-02", periods=60)
    for ticker, base, drift, pe, roe in [
        ("AAA", 100.0, 0.002, 18.0, 0.25),
        ("BBB", 50.0, 0.001, 22.0, 0.20),
        ("CCC", 200.0, 0.003, 15.0, 0.30),
    ]:
        np.random.seed(hash(ticker) % 2**31)
        prices = base * (1 + np.random.normal(drift, 0.015, len(dates))).cumprod()
        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices * 0.99, "high": prices * 1.01,
            "low": prices * 0.98, "close": prices,
            "volume": [1000000] * len(dates),
        })
        store.upsert_prices(ticker, df, source="test")

        ret_90d = (prices[-1] - prices[0]) / prices[0]
        store._conn.execute(
            "INSERT OR REPLACE INTO ticker_info VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, 5_000_000_000, "Technology", "US", 1_000_000, float(prices[-1])),
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals (ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", pe, roe),
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics VALUES (?, ?, ?, ?)",
            (ticker, float(ret_90d), 0.15, 0.5),
        )
    store._conn.commit()
    store.close()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "stockpicker" in result.stdout.lower() or "stock" in result.stdout.lower()


def test_cli_ingest_help():
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout.lower()


def test_cli_screen_run(tmp_path: Path):
    db_path = tmp_path / "test.db"
    _seed_full_db(db_path)

    screen_yaml = tmp_path / "screen.yaml"
    screen_yaml.write_text(
        "name: Test Screen\nfilters:\n  sector: [Technology]\n"
    )

    result = runner.invoke(app, [
        "screen", "run", "--config", str(screen_yaml), "--db-path", str(db_path)
    ])
    assert result.exit_code == 0
    assert "3 tickers" in result.stdout


def test_cli_score_run(tmp_path: Path):
    db_path = tmp_path / "test.db"
    _seed_full_db(db_path)

    screen_yaml = tmp_path / "screen.yaml"
    screen_yaml.write_text(
        "name: Test Screen\nfilters:\n  sector: [Technology]\n"
    )
    model_yaml = tmp_path / "model.yaml"
    model_yaml.write_text(
        "name: test-model\n"
        "factors:\n"
        "  - name: value\n"
        "    metric: pe_ratio\n"
        "    weight: 0.5\n"
        "    direction: lower_is_better\n"
        "  - name: momentum\n"
        "    metric: price_return_90d\n"
        "    weight: 0.5\n"
        "    direction: higher_is_better\n"
    )

    result = runner.invoke(app, [
        "score", "run",
        "--screen", str(screen_yaml),
        "--model", str(model_yaml),
        "--db-path", str(db_path),
    ])
    assert result.exit_code == 0
    assert "Scored" in result.stdout


def test_cli_backtest_run(tmp_path: Path):
    db_path = tmp_path / "test.db"
    _seed_full_db(db_path)

    screen_yaml = tmp_path / "configs" / "screens" / "test-screen.yaml"
    screen_yaml.parent.mkdir(parents=True, exist_ok=True)
    screen_yaml.write_text(
        "name: Test Screen\nfilters:\n  sector: [Technology]\n"
    )
    model_yaml = tmp_path / "configs" / "models" / "test-model.yaml"
    model_yaml.parent.mkdir(parents=True, exist_ok=True)
    model_yaml.write_text(
        "name: test-model\n"
        "factors:\n"
        "  - name: value\n"
        "    metric: pe_ratio\n"
        "    weight: 0.5\n"
        "    direction: lower_is_better\n"
        "  - name: momentum\n"
        "    metric: price_return_90d\n"
        "    weight: 0.5\n"
        "    direction: higher_is_better\n"
    )
    strategy_yaml = tmp_path / "strategy.yaml"
    strategy_yaml.write_text(
        "name: test-strat\n"
        "screen: test-screen\n"
        "model: test-model\n"
        "rules:\n"
        "  buy:\n"
        "    top_n: 3\n"
        "    position_size: equal\n"
        "  sell:\n"
        "    hold_days: 20\n"
        "    stop_loss: -0.10\n"
        "  portfolio:\n"
        "    initial_capital: 100000\n"
        "    max_positions: 3\n"
        "    max_position_pct: 0.4\n"
        "  costs:\n"
        "    commission_per_trade: 0.0\n"
        "    slippage_bps: 5\n"
    )

    # Note: backtest CLI resolves screen/model paths relative to configs/ dir.
    # We need to run from tmp_path so configs/screens/ and configs/models/ resolve.
    import os
    orig_dir = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, [
            "backtest", "run",
            "--strategy", str(strategy_yaml),
            "--start", "2024-01-02",
            "--end", "2024-03-01",
            "--db-path", str(db_path),
        ])
    finally:
        os.chdir(orig_dir)

    assert result.exit_code == 0
    assert "Backtest" in result.stdout
    assert "total_return" in result.stdout or "Total trades" in result.stdout


def test_cli_paper_start_and_status(tmp_path: Path):
    db_path = tmp_path / "test.db"
    _seed_full_db(db_path)

    strategy_yaml = tmp_path / "strategy.yaml"
    strategy_yaml.write_text(
        "name: test-paper\n"
        "screen: test\n"
        "model: test\n"
        "rules:\n"
        "  buy:\n"
        "    top_n: 2\n"
        "  sell:\n"
        "    hold_days: 10\n"
        "    stop_loss: -0.10\n"
        "  portfolio:\n"
        "    initial_capital: 50000\n"
        "  costs:\n"
        "    commission_per_trade: 0.0\n"
        "    slippage_bps: 0\n"
    )

    # Start
    result = runner.invoke(app, [
        "paper", "start", "--strategy", str(strategy_yaml), "--db-path", str(db_path)
    ])
    assert result.exit_code == 0
    assert "session started" in result.stdout.lower()

    # Extract session ID from output
    for line in result.stdout.splitlines():
        if "session started" in line.lower():
            session_id = line.split(":")[-1].strip()
            break
    else:
        session_id = None

    assert session_id is not None

    # Status
    result = runner.invoke(app, [
        "paper", "status", "--session", session_id, "--db-path", str(db_path)
    ])
    assert result.exit_code == 0
    assert "50,000" in result.stdout or "50000" in result.stdout

    # Stop
    result = runner.invoke(app, [
        "paper", "stop", "--session", session_id, "--db-path", str(db_path)
    ])
    assert result.exit_code == 0
    assert "stopped" in result.stdout.lower()
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_cli_integration.py -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: add CLI integration tests using Typer CliRunner"
```

---

### Task 21: Backtest Golden-File Regression Test

**Files:**
- Create: `tests/fixtures/golden_backtest_prices.csv`
- Create: `tests/fixtures/golden_backtest_expected.json`
- Create: `tests/test_backtest_regression.py`

A deterministic backtest over fixed fixture data must produce an exact equity curve. This catches silent backtester bugs that produce misleading results.

- [ ] **Step 1: Create fixture price data**

Create `tests/fixtures/golden_backtest_prices.csv`:

```csv
ticker,date,open,high,low,close,volume
GOLD1,2024-01-02,100.00,101.00,99.00,100.50,1000000
GOLD1,2024-01-03,100.50,102.00,100.00,101.00,1000000
GOLD1,2024-01-04,101.00,103.00,100.50,102.50,1000000
GOLD1,2024-01-05,102.50,104.00,102.00,103.00,1000000
GOLD1,2024-01-08,103.00,105.00,102.50,104.00,1000000
GOLD1,2024-01-09,104.00,106.00,103.50,105.50,1000000
GOLD1,2024-01-10,105.50,107.00,105.00,106.00,1000000
GOLD1,2024-01-11,106.00,108.00,105.50,107.00,1000000
GOLD1,2024-01-12,107.00,108.50,106.50,108.00,1000000
GOLD1,2024-01-15,108.00,109.00,107.00,108.50,1000000
GOLD2,2024-01-02,50.00,51.00,49.50,50.50,500000
GOLD2,2024-01-03,50.50,51.50,50.00,51.00,500000
GOLD2,2024-01-04,51.00,52.00,50.50,51.50,500000
GOLD2,2024-01-05,51.50,52.50,51.00,52.00,500000
GOLD2,2024-01-08,52.00,53.00,51.50,52.50,500000
GOLD2,2024-01-09,52.50,53.50,52.00,53.00,500000
GOLD2,2024-01-10,53.00,54.00,52.50,53.50,500000
GOLD2,2024-01-11,53.50,54.50,53.00,54.00,500000
GOLD2,2024-01-12,54.00,55.00,53.50,54.50,500000
GOLD2,2024-01-15,54.50,55.50,54.00,55.00,500000
```

- [ ] **Step 2: Write regression test (generates golden file on first run)**

Create `tests/test_backtest_regression.py`:

```python
"""Golden-file regression test for the backtester.

On first run, this generates the expected output file.
On subsequent runs, it verifies the backtester produces identical results.
"""
import json
from pathlib import Path

import pandas as pd

from stockpicker.config.models import (
    StrategyConfig, StrategyRules, BuyRules, SellRules, PortfolioRules, CostRules,
)
from stockpicker.db.store import Store
from stockpicker.engine.backtester import Backtester

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PRICES = FIXTURES / "golden_backtest_prices.csv"
GOLDEN_EXPECTED = FIXTURES / "golden_backtest_expected.json"


def _setup_golden_db(tmp_path: Path) -> Store:
    store = Store(tmp_path / "golden.db")
    prices_df = pd.read_csv(GOLDEN_PRICES)
    for ticker in prices_df["ticker"].unique():
        ticker_df = prices_df[prices_df["ticker"] == ticker].drop(columns=["ticker"])
        store.upsert_prices(ticker, ticker_df, source="golden")
    return store


def _run_golden_backtest(store: Store):
    rules = StrategyRules(
        buy=BuyRules(top_n=2, position_size="equal"),
        sell=SellRules(hold_days=5, stop_loss=-0.10),
        portfolio=PortfolioRules(initial_capital=10000, max_positions=2, max_position_pct=0.5),
        costs=CostRules(commission_per_trade=1.0, slippage_bps=10),
    )
    config = StrategyConfig(name="golden-test", screen="test", model="test", rules=rules)
    rankings = {
        "2024-01-02": ["GOLD1", "GOLD2"],
        "2024-01-03": ["GOLD1", "GOLD2"],
        "2024-01-04": ["GOLD1", "GOLD2"],
        "2024-01-05": ["GOLD1", "GOLD2"],
        "2024-01-08": ["GOLD1", "GOLD2"],
        "2024-01-09": ["GOLD1", "GOLD2"],
        "2024-01-10": ["GOLD1", "GOLD2"],
        "2024-01-11": ["GOLD1", "GOLD2"],
        "2024-01-12": ["GOLD1", "GOLD2"],
        "2024-01-15": ["GOLD1", "GOLD2"],
    }
    backtester = Backtester(store)
    return backtester.run(config=config, rankings=rankings, start="2024-01-02", end="2024-01-15")


def test_backtest_golden_file(tmp_path: Path):
    store = _setup_golden_db(tmp_path)
    result = _run_golden_backtest(store)

    actual = {
        "metrics": result.metrics,
        "equity_curve": result.equity_curve["equity"].round(2).tolist(),
        "trade_count": len(result.trades),
    }

    if not GOLDEN_EXPECTED.exists():
        # First run: generate the golden file
        GOLDEN_EXPECTED.write_text(json.dumps(actual, indent=2))
        print(f"Golden file generated at {GOLDEN_EXPECTED}")
        print(f"Metrics: {actual['metrics']}")
        print(f"Review and commit this file to lock in the expected output.")
        return

    # Subsequent runs: compare against golden file
    expected = json.loads(GOLDEN_EXPECTED.read_text())

    assert actual["trade_count"] == expected["trade_count"], (
        f"Trade count mismatch: {actual['trade_count']} != {expected['trade_count']}"
    )

    assert actual["equity_curve"] == expected["equity_curve"], (
        f"Equity curve mismatch.\n"
        f"Actual:   {actual['equity_curve']}\n"
        f"Expected: {expected['equity_curve']}"
    )

    for key in expected["metrics"]:
        assert abs(actual["metrics"][key] - expected["metrics"][key]) < 1e-4, (
            f"Metric '{key}' mismatch: {actual['metrics'][key]} != {expected['metrics'][key]}"
        )

    store.close()
```

- [ ] **Step 3: Run test (first run generates golden file)**

```bash
uv run pytest tests/test_backtest_regression.py -v -s
```

Expected: PASS — generates `tests/fixtures/golden_backtest_expected.json`. Review the output.

- [ ] **Step 4: Run test again (validates against golden file)**

```bash
uv run pytest tests/test_backtest_regression.py -v
```

Expected: PASS — deterministic output matches golden file.

- [ ] **Step 5: Commit including golden files**

```bash
git add tests/fixtures/golden_backtest_prices.csv tests/fixtures/golden_backtest_expected.json tests/test_backtest_regression.py
git commit -m "test: add golden-file backtest regression test"
```

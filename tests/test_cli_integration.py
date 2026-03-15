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
        "(ticker TEXT PRIMARY KEY, market_cap REAL, sector TEXT, country TEXT, avg_volume REAL, last_price REAL, "
        "updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    store._conn.execute(
        "CREATE TABLE IF NOT EXISTS computed_metrics "
        "(ticker TEXT PRIMARY KEY, price_return_90d REAL, revenue_growth_yoy REAL, news_sentiment_30d REAL, "
        "updated_at TEXT NOT NULL DEFAULT (datetime('now')))"
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
            "INSERT OR REPLACE INTO ticker_info "
            "(ticker, market_cap, sector, country, avg_volume, last_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, 5_000_000_000, "Technology", "US", 1_000_000, float(prices[-1])),
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO fundamentals "
            "(ticker, quarter, pe_ratio, roe) VALUES (?, ?, ?, ?)",
            (ticker, "2024-Q1", pe, roe),
        )
        store._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics "
            "(ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
            "VALUES (?, ?, ?, ?)",
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

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

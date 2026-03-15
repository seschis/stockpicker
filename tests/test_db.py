import sqlite3
from pathlib import Path

from stockpicker.db.store import Store


def test_store_creates_db_and_runs_migrations(tmp_path: Path):
    db_path = tmp_path / "test.db"
    Store(db_path)  # triggers migrations
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
    Store(db_path)  # first init triggers migrations
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
    count_after_first = cursor.fetchone()[0]
    conn.close()

    Store(db_path)  # second init should not re-apply migrations
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
    count_after_second = cursor.fetchone()[0]
    conn.close()

    assert count_after_second == count_after_first


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


def test_store_get_ticker_info(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.upsert_ticker_info("AAPL", 3e12, "Technology", "US", 5e7, 190.0)
    store.upsert_ticker_info("MSFT", 2.8e12, "Technology", "US", 3e7, 380.0)
    df = store.get_ticker_info()
    assert len(df) == 2
    assert set(df["ticker"].tolist()) == {"AAPL", "MSFT"}


def test_store_get_factor_values_latest_quarter(tmp_path: Path):
    import pandas as pd

    store = Store(tmp_path / "test.db")
    store.upsert_fundamentals("AAPL", pd.DataFrame({
        "quarter": ["2024-Q1", "2024-Q2"],
        "pe_ratio": [25.0, 30.0],
    }), source="test")
    df = store.get_factor_values("fundamentals", "pe_ratio", ["AAPL"])
    assert len(df) == 1
    assert float(df.iloc[0]["pe_ratio"]) == 30.0


def test_store_paper_session_lifecycle(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.create_paper_session("sess1", "strat1", 100000.0)

    session = store.get_paper_session("sess1")
    assert session is not None
    assert session["cash"] == 100000.0
    assert session["status"] == "active"

    store.update_paper_session_cash("sess1", 95000.0)
    session = store.get_paper_session("sess1")
    assert session["cash"] == 95000.0

    store.update_paper_session_status("sess1", "stopped")
    session = store.get_paper_session("sess1")
    assert session["status"] == "stopped"


def test_store_paper_positions_crud(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    store.create_paper_session("sess1", "strat1", 100000.0)

    store.create_paper_position("sess1", "AAPL", 10.0, 150.0, "2024-01-02")
    store.create_paper_position("sess1", "MSFT", 5.0, 350.0, "2024-01-02")

    positions = store.get_paper_positions("sess1")
    assert len(positions) == 2

    store.delete_paper_position("sess1", "AAPL")
    positions = store.get_paper_positions("sess1")
    assert len(positions) == 1
    assert positions[0]["ticker"] == "MSFT"


def test_store_save_signals_bulk(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    signals = [
        {"ticker": "AAPL", "date": "2024-01-02", "model_id": "m1", "run_id": "r1",
         "factor_name": "value", "raw_value": 25.0, "normalized_value": 0.8, "composite_score": 0.75},
        {"ticker": "MSFT", "date": "2024-01-02", "model_id": "m1", "run_id": "r1",
         "factor_name": "value", "raw_value": 30.0, "normalized_value": 0.6, "composite_score": 0.65},
        {"ticker": "GOOG", "date": "2024-01-02", "model_id": "m1", "run_id": "r1",
         "factor_name": "value", "raw_value": 20.0, "normalized_value": 0.9, "composite_score": 0.85},
    ]
    store.save_signals(signals)
    df = store.get_signals("m1")
    assert len(df) == 3

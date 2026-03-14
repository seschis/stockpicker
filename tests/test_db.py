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
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM schema_version")
    count_after_first = cursor.fetchone()[0]
    conn.close()

    store2 = Store(db_path)  # should not fail or re-apply migrations
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

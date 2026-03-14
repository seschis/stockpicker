import logging
import sqlite3
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

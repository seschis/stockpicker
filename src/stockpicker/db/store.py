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
        rows = [
            (ticker, row["date"], row["open"], row["high"], row["low"], row["close"], int(row["volume"]), source)  # pyright: ignore[reportArgumentType]
            for _, row in df.iterrows()
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close, volume, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
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
            "(ticker, quarter, eps, pe_ratio, revenue, gross_margin, "
            "operating_margin, roe, debt_to_equity, free_cash_flow, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def get_fundamentals(self, ticker: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM fundamentals WHERE ticker = ? ORDER BY quarter", self._conn, params=[ticker]
        )

    def save_signals(self, records: list[dict]) -> None:
        rows = [
            (r["ticker"], r["date"], r["model_id"], r["run_id"], r["factor_name"],
             r.get("raw_value"), r.get("normalized_value"), r.get("composite_score"))
            for r in records
        ]
        self._conn.executemany(
            "INSERT OR REPLACE INTO signals "
            "(ticker, date, model_id, run_id, factor_name, raw_value, normalized_value, composite_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def save_trade(self, trade: dict) -> None:
        self._conn.execute(
            "INSERT INTO trades (strategy_id, session_type, session_id, "
            "ticker, action, date, price, shares, commission, slippage) "
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

    def upsert_ticker_info(
        self, ticker: str, market_cap: float | None, sector: str, country: str, avg_volume: float, last_price: float,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO ticker_info (ticker, market_cap, sector, country, avg_volume, last_price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticker, market_cap, sector, country, avg_volume, last_price),
        )
        self._conn.commit()

    def upsert_computed_metrics(
        self,
        ticker: str,
        price_return_90d: float | None,
        revenue_growth_yoy: float | None,
        news_sentiment_30d: float | None,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO computed_metrics "
            "(ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d) "
            "VALUES (?, ?, ?, ?)",
            (ticker, price_return_90d, revenue_growth_yoy, news_sentiment_30d),
        )
        self._conn.commit()

    def get_ticker_info(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM ticker_info", self._conn)

    def get_signals(self, model_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM signals WHERE model_id = ? ORDER BY date DESC",
            self._conn, params=[model_id],
        )

    def get_factor_values(self, table: str, column: str, tickers: list[str]) -> pd.DataFrame:
        placeholders = ",".join("?" for _ in tickers)
        if table == "fundamentals":
            query = (
                f"SELECT ticker, {column} FROM {table} "
                f"WHERE ticker IN ({placeholders}) "
                f"AND (ticker, quarter) IN "
                f"(SELECT ticker, MAX(quarter) FROM {table} GROUP BY ticker)"
            )
        else:
            query = f"SELECT ticker, {column} FROM {table} WHERE ticker IN ({placeholders})"
        return pd.read_sql_query(query, self._conn, params=tickers)

    def create_paper_session(self, session_id: str, strategy_id: str, cash: float) -> None:
        self._conn.execute(
            "INSERT INTO paper_sessions (session_id, strategy_id, status, cash) VALUES (?, ?, ?, ?)",
            (session_id, strategy_id, "active", cash),
        )
        self._conn.commit()

    def get_paper_session(self, session_id: str) -> dict | None:
        cursor = self._conn.execute(
            "SELECT * FROM paper_sessions WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_paper_positions(self, session_id: str) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT * FROM paper_positions WHERE session_id = ?", (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_paper_position(self, session_id: str, ticker: str) -> None:
        self._conn.execute(
            "DELETE FROM paper_positions WHERE session_id = ? AND ticker = ?",
            (session_id, ticker),
        )
        self._conn.commit()

    def create_paper_position(
        self, session_id: str, ticker: str, shares: float, entry_price: float, entry_date: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO paper_positions (session_id, ticker, shares, entry_price, entry_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, ticker, shares, entry_price, entry_date),
        )
        self._conn.commit()

    def update_paper_session_cash(self, session_id: str, cash: float) -> None:
        self._conn.execute(
            "UPDATE paper_sessions SET cash = ? WHERE session_id = ?", (cash, session_id)
        )
        self._conn.commit()

    def update_paper_session_status(self, session_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE paper_sessions SET status = ? WHERE session_id = ?", (status, session_id)
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

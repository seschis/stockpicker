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

CREATE TABLE IF NOT EXISTS ticker_info (
    ticker TEXT PRIMARY KEY,
    market_cap REAL,
    sector TEXT,
    country TEXT,
    avg_volume REAL,
    last_price REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

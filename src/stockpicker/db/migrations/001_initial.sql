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

CREATE TABLE IF NOT EXISTS computed_metrics (
    ticker TEXT PRIMARY KEY,
    price_return_90d REAL,
    revenue_growth_yoy REAL,
    news_sentiment_30d REAL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

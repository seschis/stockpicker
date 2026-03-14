"""Maps metric names to (table, column) pairs for data retrieval."""

METRIC_SOURCES: dict[str, tuple[str, str]] = {
    "pe_ratio": ("fundamentals", "pe_ratio"),
    "eps": ("fundamentals", "eps"),
    "revenue": ("fundamentals", "revenue"),
    "gross_margin": ("fundamentals", "gross_margin"),
    "operating_margin": ("fundamentals", "operating_margin"),
    "roe": ("fundamentals", "roe"),
    "return_on_equity": ("fundamentals", "roe"),
    "debt_to_equity": ("fundamentals", "debt_to_equity"),
    "free_cash_flow": ("fundamentals", "free_cash_flow"),
    "revenue_growth_yoy": ("computed_metrics", "revenue_growth_yoy"),
    "price_return_90d": ("computed_metrics", "price_return_90d"),
    "news_sentiment_30d": ("computed_metrics", "news_sentiment_30d"),
}

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import typer

from stockpicker.db.store import Store
from stockpicker.engine.ingester import Ingester
from stockpicker.engine.metrics_computer import MetricsComputer
from stockpicker.sources.yfinance_source import YFinanceSource

ingest_app = typer.Typer(help="Ingest market data from configured sources.")


@ingest_app.command("run")
def ingest_run(
    tickers: list[str] = typer.Argument(..., help="Ticker symbols to ingest"),
    start: Optional[str] = typer.Option(None, help="Start date (YYYY-MM-DD). Default: 1 year ago."),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Default: today."),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Ingest price and fundamental data for given tickers."""
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    store = Store(db_path)
    sources = {"yfinance": YFinanceSource()}
    ingester = Ingester(store=store, sources=sources)

    results = ingester.ingest(tickers=tickers, start=start_date, end=end_date)

    for ticker, info in results.items():
        typer.echo(f"{ticker}: {info['prices']} prices, {info['fundamentals']} fundamentals")
        if "error" in info:
            typer.echo(f"  Warning: {info['error']}", err=True)

    computer = MetricsComputer(store)
    computer.compute_all(tickers)
    typer.echo("Computed derived metrics.")

    store.close()

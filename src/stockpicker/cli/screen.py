from pathlib import Path

import typer

from stockpicker.config.loader import load_screen
from stockpicker.db.store import Store
from stockpicker.engine.screener import Screener

screen_app = typer.Typer(help="Screen stocks by criteria.")


@screen_app.command("run")
def screen_run(
    config: Path = typer.Option(..., "--config", "-c", help="Path to screen YAML config"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Filter stock universe by screening criteria."""
    screen_config = load_screen(config)
    store = Store(db_path)
    screener = Screener(store)
    result = screener.screen(screen_config)

    typer.echo(f"\nScreen: {screen_config.name}")
    typer.echo(f"Results: {len(result)} tickers\n")
    if not result.empty:
        typer.echo(result[["ticker", "market_cap", "sector", "last_price"]].to_string(index=False))

    store.close()

import typer

from stockpicker.logging_config import setup_logging

app = typer.Typer(
    name="stockpicker",
    help="Stock analysis, scoring, backtesting, and paper trading CLI.",
)


@app.callback()
def main(
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
) -> None:
    """Stockpicker CLI."""
    setup_logging(verbosity=verbose)

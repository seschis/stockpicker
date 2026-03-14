import typer

from stockpicker.cli.ingest import ingest_app
from stockpicker.cli.score import score_app
from stockpicker.cli.screen import screen_app
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


app.add_typer(ingest_app, name="ingest")
app.add_typer(screen_app, name="screen")
app.add_typer(score_app, name="score")

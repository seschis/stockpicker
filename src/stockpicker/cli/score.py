from pathlib import Path

import typer

from stockpicker.config.loader import load_model, load_screen
from stockpicker.db.store import Store
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.screener import Screener

score_app = typer.Typer(help="Score stocks using factor models.")


@score_app.command("run")
def score_run(
    screen: str = typer.Option(..., "--screen", "-s", help="Screen config name or path"),
    model: str = typer.Option(..., "--model", "-m", help="Model config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
    top_n: int = typer.Option(20, "--top", "-n", help="Show top N results"),
) -> None:
    """Score screened stocks with a factor model."""
    screen_path = Path(f"configs/screens/{screen}.yaml") if not Path(screen).exists() else Path(screen)
    model_path = Path(f"configs/models/{model}.yaml") if not Path(model).exists() else Path(model)

    screen_config = load_screen(screen_path)
    model_config = load_model(model_path)

    store = Store(db_path)
    screener = Screener(store)
    screened = screener.screen(screen_config)

    if screened.empty:
        typer.echo("No tickers passed screening.")
        raise typer.Exit(1)

    tickers = screened["ticker"].tolist()
    scorer = Scorer(store)
    result = scorer.score(tickers=tickers, model=model_config)

    typer.echo(f"\nModel: {model_config.name}")
    typer.echo(f"Scored: {len(result)} tickers\n")
    if not result.empty:
        typer.echo(result.head(top_n).to_string(index=False))

    store.close()

from pathlib import Path

import typer

from stockpicker.config.loader import load_model, load_screen, load_strategy
from stockpicker.db.store import Store
from stockpicker.engine.backtester import Backtester
from stockpicker.engine.scorer import Scorer
from stockpicker.engine.screener import Screener

backtest_app = typer.Typer(help="Backtest trading strategies.")


@backtest_app.command("run")
def backtest_run(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    start: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Run a backtest for a trading strategy."""
    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)

    store = Store(db_path)

    # Load screen and model
    screen_path = Path(f"configs/screens/{config.screen}.yaml")
    model_path = Path(f"configs/models/{config.model}.yaml")
    screen_config = load_screen(screen_path)
    model_config = load_model(model_path)

    # Screen tickers
    screener = Screener(store)
    screened = screener.screen(screen_config)
    if screened.empty:
        typer.echo("No tickers passed screening.")
        raise typer.Exit(1)

    tickers = screened["ticker"].tolist()

    # Score to build rankings (use same ranking for all dates in simple mode)
    scorer = Scorer(store)
    scored = scorer.score(tickers=tickers, model=model_config)
    if scored.empty:
        typer.echo("Scoring produced no results.")
        raise typer.Exit(1)

    ranked_tickers = scored["ticker"].tolist()

    # Build rankings dict — same ranking for all trading days
    import pandas as pd
    trading_dates = pd.bdate_range(start, end)
    rankings = {d.strftime("%Y-%m-%d"): ranked_tickers for d in trading_dates}

    # Run backtest
    backtester = Backtester(store)
    result = backtester.run(config=config, rankings=rankings, start=start, end=end)

    # Print results
    typer.echo(f"\n{'='*50}")
    typer.echo(f"Backtest: {config.name}")
    typer.echo(f"Period: {start} to {end}")
    typer.echo(f"{'='*50}\n")

    for key, value in result.metrics.items():
        if "return" in key or "drawdown" in key:
            typer.echo(f"  {key}: {value:.2%}")
        else:
            typer.echo(f"  {key}: {value}")

    typer.echo(f"\n  Total trades: {len(result.trades)}")

    # Print benchmark comparisons
    if result.benchmark_metrics:
        strategy_return = result.metrics.get("total_return", 0.0)
        typer.echo("\n--- Benchmarks ---")
        for ticker, bench in result.benchmark_metrics.items():
            bench_return = bench.get("total_return", 0.0)
            excess = strategy_return - bench_return
            sign = "+" if excess >= 0 else ""
            typer.echo(f"  {ticker} (buy & hold): {bench_return:.2%}    excess: {sign}{excess:.2%}")

    store.close()

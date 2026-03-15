from pathlib import Path

import typer

from stockpicker.config.loader import load_strategy
from stockpicker.db.store import Store
from stockpicker.engine.paper_trader import PaperTrader

paper_app = typer.Typer(help="Paper trade strategies with simulated capital.")


@paper_app.command("start")
def paper_start(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Start a new paper trading session."""
    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)
    store = Store(db_path)
    trader = PaperTrader(store)
    session_id = trader.start(config)
    typer.echo(f"Paper trading session started: {session_id}")
    typer.echo(f"Strategy: {config.name}")
    typer.echo(f"Initial capital: ${config.rules.portfolio.initial_capital:,.2f}")
    typer.echo(f"\nRun 'stockpicker paper run-cycle --session {session_id}' daily to advance.")
    store.close()


@paper_app.command("status")
def paper_status(
    session: str = typer.Option(..., "--session", help="Session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Show current paper trading status."""
    store = Store(db_path)
    trader = PaperTrader(store)
    status = trader.status(session)
    typer.echo(f"\nSession: {status['session_id']}")
    typer.echo(f"Strategy: {status['strategy_id']}")
    typer.echo(f"Status: {status['status']}")
    typer.echo(f"Cash: ${status['cash']:,.2f}")
    typer.echo(f"Positions: {len(status['positions'])}")
    for pos in status["positions"]:
        typer.echo(f"  {pos['ticker']}: {pos['shares']:.2f} shares @ ${pos['entry_price']:.2f}")
    store.close()


@paper_app.command("run-cycle")
def paper_run_cycle(
    session: str = typer.Option(..., "--session", help="Session ID"),
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy config name or path"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Run one paper trading cycle (designed to be called via cron)."""
    from datetime import date as date_cls
    from datetime import timedelta

    from stockpicker.config.loader import load_model, load_screen, load_strategy
    from stockpicker.engine.ingester import Ingester
    from stockpicker.engine.scorer import Scorer
    from stockpicker.engine.screener import Screener
    from stockpicker.sources.yfinance_source import YFinanceSource

    strat_path = Path(f"configs/strategies/{strategy}.yaml") if not Path(strategy).exists() else Path(strategy)
    config = load_strategy(strat_path)
    store = Store(db_path)

    today = date_cls.today()

    # 1. Ingest fresh data
    screen_path = Path(f"configs/screens/{config.screen}.yaml")
    screen_config = load_screen(screen_path)
    screener = Screener(store)
    screened = screener.screen(screen_config)
    tickers = screened["ticker"].tolist() if not screened.empty else []

    sources = {"yfinance": YFinanceSource()}
    ingester = Ingester(store=store, sources=sources)
    ingester.ingest(tickers=tickers, start=today - timedelta(days=7), end=today)

    # 2. Score
    model_path = Path(f"configs/models/{config.model}.yaml")
    model_config = load_model(model_path)
    scorer = Scorer(store)
    scored = scorer.score(tickers=tickers, model=model_config)
    rankings = scored["ticker"].tolist() if not scored.empty else []

    # 3. Get current prices
    prices = {}
    for ticker in tickers:
        p = store.get_prices(ticker, start=today.isoformat(), end=today.isoformat())
        if not p.empty:
            prices[ticker] = float(p.iloc[-1]["close"])

    # 4. Execute cycle
    trader = PaperTrader(store)
    result = trader.run_cycle(session, rankings, prices, today.isoformat(), config)

    typer.echo(f"\nPaper trade cycle: {today}")
    typer.echo(f"  Actions: {len(result.get('actions', []))}")
    for action in result.get("actions", []):
        typer.echo(f"    {action['action']} {action['ticker']} @ ${action['price']:.2f}")
    typer.echo(f"  Cash: ${result.get('cash', 0):,.2f}")
    typer.echo(f"  Positions: {result.get('positions', 0)}")
    store.close()


@paper_app.command("stop")
def paper_stop(
    session: str = typer.Option(..., "--session", help="Session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Stop a paper trading session."""
    store = Store(db_path)
    trader = PaperTrader(store)
    result = trader.stop(session)
    typer.echo(f"Session {session} stopped. Final cash: ${result['cash']:,.2f}")
    store.close()

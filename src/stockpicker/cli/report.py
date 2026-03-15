from pathlib import Path

import pandas as pd
import typer

from stockpicker.db.store import Store
from stockpicker.engine.reporter import Reporter

report_app = typer.Typer(help="Generate performance reports.")


def _reconstruct_equity_curve(
    store: Store, strategy_id: str, session_id: str | None,
) -> tuple[pd.DataFrame, list[dict], float]:
    """Rebuild equity curve from trade log. Returns (equity_df, trades, initial_capital)."""
    trades_df = store.get_trades(strategy_id=strategy_id, session_id=session_id)
    if trades_df.empty:
        return pd.DataFrame(), [], 0.0
    trades = trades_df.to_dict("records")

    # Determine initial capital from first buy total
    buys = [t for t in trades if t["action"] == "BUY"]
    if not buys:
        return pd.DataFrame(), trades, 0.0
    # Estimate initial capital: sum of first batch of buys
    first_date = buys[0]["date"]
    first_buys = [b for b in buys if b["date"] == first_date]
    initial_capital = sum(b["price"] * b["shares"] + b.get("commission", 0) for b in first_buys) * 2  # rough estimate

    # Build daily equity from trades and price data
    all_dates = sorted(set(t["date"] for t in trades))
    if len(all_dates) < 2:
        return pd.DataFrame({"date": all_dates, "equity": [initial_capital]}), trades, initial_capital

    # Get price range
    start, end = all_dates[0], all_dates[-1]
    all_trading_dates = pd.bdate_range(start, end).strftime("%Y-%m-%d").tolist()

    cash = initial_capital
    positions: dict[str, tuple[float, float]] = {}  # ticker -> (shares, entry_price)
    equity_records = []
    trade_idx = 0

    for date in all_trading_dates:
        while trade_idx < len(trades) and trades[trade_idx]["date"] == date:
            t = trades[trade_idx]
            if t["action"] == "BUY":
                cost = t["price"] * t["shares"] + t.get("commission", 0)
                cash -= cost
                prev = positions.get(t["ticker"], (0.0, 0.0))
                positions[t["ticker"]] = (prev[0] + t["shares"], t["price"])
            elif t["action"] == "SELL":
                proceeds = t["price"] * t["shares"] - t.get("commission", 0)
                cash += proceeds
                if t["ticker"] in positions:
                    remaining = positions[t["ticker"]][0] - t["shares"]
                    if remaining <= 0.01:
                        del positions[t["ticker"]]
                    else:
                        positions[t["ticker"]] = (remaining, positions[t["ticker"]][1])
            trade_idx += 1

        portfolio_value = cash
        for ticker, (shares, _) in positions.items():
            prices = store.get_prices(ticker, start=date, end=date)
            if not prices.empty:
                portfolio_value += float(prices.iloc[0]["close"]) * shares
        equity_records.append({"date": date, "equity": portfolio_value})

    return pd.DataFrame(equity_records), trades, initial_capital


@report_app.command("strategy")
def report_strategy(
    strategy: str = typer.Option(..., "--strategy", "-s", help="Strategy name"),
    session_id: str | None = typer.Option(None, "--session", help="Specific session ID"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Show performance report for a strategy."""
    store = Store(db_path)
    equity_df, trades, initial_capital = _reconstruct_equity_curve(store, strategy, session_id)

    if not trades:
        typer.echo(f"No trades found for strategy '{strategy}'")
        raise typer.Exit(1)

    reporter = Reporter()
    if not equity_df.empty and initial_capital > 0:
        report = reporter.strategy_report(strategy, equity_df, trades, initial_capital)
        typer.echo(reporter.format_report(report))
    else:
        typer.echo(f"\n{strategy}: {len(trades)} trades (insufficient data for full metrics)")

    store.close()


@report_app.command("compare")
def report_compare(
    strategies: str = typer.Option(..., "--compare", help="Comma-separated strategy names"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Compare multiple strategies side by side."""
    store = Store(db_path)
    names = [s.strip() for s in strategies.split(",")]
    reporter = Reporter()
    reports = {}

    for name in names:
        equity_df, trades, initial_capital = _reconstruct_equity_curve(store, name, None)
        if trades and not equity_df.empty and initial_capital > 0:
            reports[name] = reporter.strategy_report(name, equity_df, trades, initial_capital)
        else:
            typer.echo(f"Warning: insufficient data for {name}")

    if reports:
        comparison = reporter.compare(reports)
        typer.echo("\nStrategy Comparison")
        typer.echo("=" * 80)
        typer.echo(comparison.to_string(index=False))

    store.close()


@report_app.command("evaluate-factors")
def report_evaluate_factors(
    model: str = typer.Option(..., "--model", "-m", help="Model name"),
    period: str = typer.Option("90d", "--period", help="Lookback period (e.g., 90d)"),
    db_path: Path = typer.Option("data/stockpicker.db", help="Path to database"),
) -> None:
    """Evaluate individual factor predictiveness."""
    store = Store(db_path)

    # Get signals for this model
    signals_df = store.get_signals(model)
    if signals_df.empty:
        typer.echo(f"No signals found for model '{model}'")
        raise typer.Exit(1)

    # Get price returns for tickers in signals
    tickers = signals_df["ticker"].unique().tolist()
    returns = {}
    for ticker in tickers:
        prices = store.get_prices(ticker)
        if len(prices) >= 2:
            closes = prices["close"].values.astype(float)
            returns[ticker] = (closes[-1] - closes[0]) / closes[0]

    reporter = Reporter()
    eval_result = reporter.factor_evaluation(signals_df, pd.Series(returns))
    typer.echo(reporter.format_factor_evaluation(eval_result))
    store.close()

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from stockpicker.config.models import StrategyConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.backtester")


@dataclass
class BacktestResult:
    metrics: dict[str, float]
    trades: list[dict[str, Any]]
    equity_curve: pd.DataFrame


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: float
    days_held: int = 0


class Backtester:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(
        self,
        config: StrategyConfig,
        rankings: dict[str, list[str]],
        start: str,
        end: str,
    ) -> BacktestResult:
        session_id = str(uuid.uuid4())[:8]
        rules = config.rules
        cash = rules.portfolio.initial_capital
        positions: dict[str, Position] = {}
        trades: list[dict] = []
        equity_history: list[dict] = []

        # Get all trading dates
        all_dates = sorted(rankings.keys())
        trading_dates = [d for d in all_dates if start <= d <= end]

        # Cache price data
        all_tickers = set()
        for ranked in rankings.values():
            all_tickers.update(ranked)
        price_cache: dict[str, pd.DataFrame] = {}
        for ticker in all_tickers:
            price_cache[ticker] = self.store.get_prices(ticker, start=start, end=end)

        def get_price(ticker: str, date: str) -> float | None:
            df = price_cache.get(ticker)
            if df is None or df.empty:
                return None
            row = df[df["date"] == date]
            if row.empty:
                return None
            return float(row.iloc[0]["close"])

        for date in trading_dates:
            # Update days held
            for pos in positions.values():
                pos.days_held += 1

            # Check stop losses and hold period exits
            to_sell = []
            for ticker, pos in positions.items():
                current_price = get_price(ticker, date)
                if current_price is None:
                    # Delisted or gap — force exit at last known price
                    to_sell.append((ticker, pos.entry_price, "DELISTED"))
                    continue
                pnl_pct = (current_price - pos.entry_price) / pos.entry_price
                if pnl_pct <= rules.sell.stop_loss:
                    to_sell.append((ticker, current_price, "STOP_LOSS"))
                elif pos.days_held >= rules.sell.hold_days:
                    to_sell.append((ticker, current_price, "HOLD_EXPIRY"))

            for ticker, sell_price, reason in to_sell:
                pos = positions.pop(ticker)
                slippage = sell_price * (rules.costs.slippage_bps / 10000)
                adj_price = sell_price - slippage
                proceeds = adj_price * pos.shares
                cash += proceeds
                trade = {
                    "strategy_id": config.name,
                    "session_type": "backtest",
                    "session_id": session_id,
                    "ticker": ticker,
                    "action": "SELL",
                    "date": date,
                    "price": adj_price,
                    "shares": pos.shares,
                    "commission": rules.costs.commission_per_trade,
                    "slippage": slippage * pos.shares,
                }
                trades.append(trade)
                cash -= rules.costs.commission_per_trade

            # Buy if we have open slots
            ranked = rankings.get(date, [])
            open_slots = rules.portfolio.max_positions - len(positions)
            candidates = [t for t in ranked if t not in positions][:rules.buy.top_n]

            for ticker in candidates[:open_slots]:
                price = get_price(ticker, date)
                if price is None:
                    continue
                slippage = price * (rules.costs.slippage_bps / 10000)
                adj_price = price + slippage
                max_by_pct = rules.portfolio.initial_capital * rules.portfolio.max_position_pct
                position_value = min(cash / max(open_slots, 1), max_by_pct)
                if position_value < adj_price:
                    continue
                shares = position_value / adj_price
                cost = adj_price * shares + rules.costs.commission_per_trade
                if cost > cash:
                    continue
                cash -= cost
                positions[ticker] = Position(
                    ticker=ticker, entry_date=date, entry_price=adj_price, shares=shares
                )
                trades.append({
                    "strategy_id": config.name,
                    "session_type": "backtest",
                    "session_id": session_id,
                    "ticker": ticker,
                    "action": "BUY",
                    "date": date,
                    "price": adj_price,
                    "shares": shares,
                    "commission": rules.costs.commission_per_trade,
                    "slippage": slippage * shares,
                })
                open_slots -= 1

            # Calculate portfolio value
            portfolio_value = cash
            for ticker, pos in positions.items():
                p = get_price(ticker, date)
                if p is not None:
                    portfolio_value += p * pos.shares

            equity_history.append({"date": date, "equity": portfolio_value, "cash": cash})

        # Compute metrics
        equity_df = pd.DataFrame(equity_history)
        metrics = self._compute_metrics(equity_df, rules.portfolio.initial_capital)

        # Save trades to DB
        for t in trades:
            self.store.save_trade(t)

        return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity_df)

    def _compute_metrics(self, equity_df: pd.DataFrame, initial_capital: float) -> dict[str, float]:
        if equity_df.empty:
            return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0}

        equity = equity_df["equity"].values
        total_return = (equity[-1] - initial_capital) / initial_capital

        # Daily returns
        returns = np.diff(equity) / equity[:-1]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0
        sortino_denom = np.std(returns[returns < 0]) if np.any(returns < 0) else 1e-10
        sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Win rate from trades
        n_days = len(equity_df)
        annualized = (1 + total_return) ** (252 / max(n_days, 1)) - 1 if n_days > 0 else 0.0

        return {
            "total_return": round(total_return, 6),
            "annualized_return": round(annualized, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_drawdown, 6),
            "trading_days": n_days,
        }

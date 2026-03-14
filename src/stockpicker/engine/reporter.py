from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("stockpicker.engine.reporter")


class Reporter:
    def strategy_report(
        self,
        name: str,
        equity_curve: pd.DataFrame,
        trades: list[dict],
        initial_capital: float,
    ) -> dict[str, Any]:
        equity = equity_curve["equity"].values

        total_return = (equity[-1] - initial_capital) / initial_capital
        n_days = len(equity)
        annualized = (1 + total_return) ** (252 / max(n_days, 1)) - 1

        returns = np.diff(equity) / equity[:-1]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0
        neg_returns = returns[returns < 0]
        sortino_denom = np.std(neg_returns) if len(neg_returns) > 0 else 1e-10
        sortino = np.mean(returns) / sortino_denom * np.sqrt(252)

        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Win rate from trade pairs
        buys = {t["ticker"]: t for t in trades if t["action"] == "BUY"}
        sells = [t for t in trades if t["action"] == "SELL"]
        wins = sum(1 for s in sells if s["ticker"] in buys and s["price"] > buys[s["ticker"]]["price"])
        total_closed = len(sells)
        win_rate = wins / total_closed if total_closed > 0 else 0.0

        return {
            "strategy": name,
            "total_return": round(total_return, 6),
            "annualized_return": round(annualized, 6),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_drawdown, 6),
            "win_rate": round(win_rate, 4),
            "total_trades": len(trades),
            "trading_days": n_days,
        }

    def compare(self, reports: dict[str, dict]) -> pd.DataFrame:
        rows = []
        for name, metrics in reports.items():
            rows.append({"strategy": name, **metrics})
        return pd.DataFrame(rows)

    def format_report(self, report: dict[str, Any]) -> str:
        lines = [
            f"Strategy: {report['strategy']}",
            f"{'='*40}",
            f"  Total Return:      {report['total_return']:.2%}",
            f"  Annualized Return: {report['annualized_return']:.2%}",
            f"  Sharpe Ratio:      {report['sharpe_ratio']:.4f}",
            f"  Sortino Ratio:     {report['sortino_ratio']:.4f}",
            f"  Max Drawdown:      {report['max_drawdown']:.2%}",
            f"  Win Rate:          {report['win_rate']:.2%}",
            f"  Total Trades:      {report['total_trades']}",
            f"  Trading Days:      {report['trading_days']}",
        ]
        return "\n".join(lines)

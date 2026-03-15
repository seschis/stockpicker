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
        downside = np.minimum(returns, 0)
        sortino_denom = np.sqrt(np.mean(downside ** 2)) if len(returns) > 0 else 1e-10
        sortino = (np.mean(returns) / sortino_denom * np.sqrt(252)) if sortino_denom > 1e-10 else 0.0

        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Win rate from chronological trade pairs (FIFO matching)
        buy_queues: dict[str, list[float]] = {}
        wins = 0
        total_closed = 0
        for t in trades:
            if t["action"] == "BUY":
                buy_queues.setdefault(t["ticker"], []).append(t["price"])
            elif t["action"] == "SELL" and buy_queues.get(t["ticker"]):
                entry_price = buy_queues[t["ticker"]].pop(0)
                total_closed += 1
                if t["price"] > entry_price:
                    wins += 1
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

    def factor_evaluation(self, signals: pd.DataFrame, returns: pd.Series) -> pd.DataFrame:
        """Evaluate factor predictiveness via information coefficient."""
        factors = signals["factor_name"].unique()
        records = []
        for factor in factors:
            factor_data = signals[signals["factor_name"] == factor].set_index("ticker")
            common = factor_data.index.intersection(returns.index)
            if len(common) < 3:
                records.append({"factor_name": factor, "ic": None, "avg_score": None})
                continue
            factor_scores = factor_data.loc[common, "normalized_value"]
            factor_returns = returns.loc[common]
            ic = factor_scores.corr(factor_returns)
            records.append({
                "factor_name": factor,
                "ic": round(ic, 4) if not pd.isna(ic) else None,
                "avg_score": round(factor_scores.mean(), 4),
            })
        return pd.DataFrame(records)

    def format_factor_evaluation(self, eval_df: pd.DataFrame) -> str:
        lines = ["Factor Evaluation", "=" * 40]
        for _, row in eval_df.iterrows():
            ic_str = f"{row['ic']:.4f}" if row["ic"] is not None else "N/A"
            lines.append(f"  {row['factor_name']}: IC={ic_str}")
        return "\n".join(lines)

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

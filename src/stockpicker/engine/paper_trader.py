from __future__ import annotations

import logging
import uuid
from typing import Any

from stockpicker.config.models import StrategyConfig
from stockpicker.db.store import Store

logger = logging.getLogger("stockpicker.engine.paper_trader")


class PaperTrader:
    def __init__(self, store: Store) -> None:
        self.store = store

    def start(self, config: StrategyConfig) -> str:
        session_id = str(uuid.uuid4())[:8]
        cash = config.rules.portfolio.initial_capital
        self.store.create_paper_session(session_id, config.name, cash)
        logger.info("Started paper session %s for strategy %s", session_id, config.name)
        return session_id

    def status(self, session_id: str) -> dict[str, Any]:
        session = self.store.get_paper_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        positions = self.store.get_paper_positions(session_id)

        return {
            "session_id": session["session_id"],
            "strategy_id": session["strategy_id"],
            "status": session["status"],
            "cash": session["cash"],
            "positions": positions,
        }

    def run_cycle(
        self, session_id: str, rankings: list[str], prices: dict[str, float],
        date: str, config: StrategyConfig,
    ) -> dict:
        """Execute one trading cycle for the paper session."""
        status = self.status(session_id)
        if status["status"] != "active":
            return {"error": "Session not active"}

        rules = config.rules
        cash = status["cash"]
        positions = {p["ticker"]: p for p in status["positions"]}
        actions: list[dict] = []

        # Check sells
        for ticker, pos in list(positions.items()):
            current_price = prices.get(ticker)
            if current_price is None:
                continue
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] if pos["entry_price"] > 0 else 0.0
            days_held = (
                len(list(self.store.get_prices(ticker, start=pos["entry_date"], end=date)))
            )

            should_sell = pnl_pct <= rules.sell.stop_loss or days_held >= rules.sell.hold_days
            if should_sell:
                slippage = current_price * (rules.costs.slippage_bps / 10000)
                adj_price = current_price - slippage
                proceeds = adj_price * pos["shares"] - rules.costs.commission_per_trade
                cash += proceeds
                self.store.delete_paper_position(session_id, ticker)
                self.store.save_trade({
                    "strategy_id": config.name, "session_type": "paper", "session_id": session_id,
                    "ticker": ticker, "action": "SELL", "date": date,
                    "price": adj_price, "shares": pos["shares"],
                    "commission": rules.costs.commission_per_trade, "slippage": slippage * pos["shares"],
                })
                del positions[ticker]
                actions.append({"action": "SELL", "ticker": ticker, "price": adj_price})

        # Check buys
        open_slots = rules.portfolio.max_positions - len(positions)
        candidates = [t for t in rankings if t not in positions][:rules.buy.top_n]

        for ticker in candidates[:open_slots]:
            price = prices.get(ticker)
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
            self.store.create_paper_position(session_id, ticker, shares, adj_price, date)
            self.store.save_trade({
                "strategy_id": config.name, "session_type": "paper", "session_id": session_id,
                "ticker": ticker, "action": "BUY", "date": date,
                "price": adj_price, "shares": shares,
                "commission": rules.costs.commission_per_trade, "slippage": slippage * shares,
            })
            positions[ticker] = {"ticker": ticker, "shares": shares, "entry_price": adj_price, "entry_date": date}
            open_slots -= 1
            actions.append({"action": "BUY", "ticker": ticker, "price": adj_price})

        # Update cash
        self.store.update_paper_session_cash(session_id, cash)

        return {"date": date, "actions": actions, "cash": cash, "positions": len(positions)}

    def stop(self, session_id: str) -> dict:
        self.store.update_paper_session_status(session_id, "stopped")
        return self.status(session_id)

from __future__ import annotations

import importlib
import logging
import uuid

import numpy as np
import pandas as pd

from stockpicker.config.models import FactorConfig, ModelConfig
from stockpicker.db.store import Store
from stockpicker.factors.builtin import METRIC_SOURCES

logger = logging.getLogger("stockpicker.engine.scorer")


class Scorer:
    def __init__(self, store: Store) -> None:
        self.store = store

    def score(self, tickers: list[str], model: ModelConfig) -> pd.DataFrame:
        run_id = str(uuid.uuid4())[:8]
        logger.info("Scoring %d tickers with model '%s' (run %s)", len(tickers), model.name, run_id)

        factor_data: dict[str, pd.Series] = {}
        active_factors: list[FactorConfig] = []

        for factor in model.factors:
            try:
                values = self._get_factor_values(tickers, factor)
                if values is not None and not values.empty:
                    factor_data[factor.name] = values
                    active_factors.append(factor)
                else:
                    logger.warning("No data for factor '%s', skipping", factor.name)
            except Exception as e:
                logger.error("Error computing factor '%s': %s", factor.name, e)

        if not active_factors:
            logger.error("No factors could be computed")
            return pd.DataFrame(columns=["ticker", "composite_score"])

        # Normalize weights for active factors
        total_weight = sum(f.weight for f in active_factors)
        weights = {f.name: f.weight / total_weight for f in active_factors}

        # Build score DataFrame
        all_tickers = set()
        for s in factor_data.values():
            all_tickers.update(s.index)

        records = []
        for ticker in all_tickers:
            composite = 0.0
            factor_scores = {}
            valid = True
            for factor in active_factors:
                if ticker not in factor_data[factor.name].index:
                    valid = False
                    break
                raw = factor_data[factor.name][ticker]
                if pd.isna(raw):
                    valid = False
                    break
                # Normalize: percentile rank
                series = factor_data[factor.name].dropna()
                rank = series.rank(pct=True)
                normalized = rank.get(ticker, np.nan)
                if factor.direction == "lower_is_better":
                    normalized = 1.0 - normalized
                factor_scores[factor.name] = normalized
                composite += normalized * weights[factor.name]

            if valid:
                records.append({"ticker": ticker, "composite_score": composite, **factor_scores})

        result = pd.DataFrame(records)
        if result.empty:
            return pd.DataFrame(columns=["ticker", "composite_score"])

        result = result.sort_values("composite_score", ascending=False).reset_index(drop=True)

        # Save signals to DB
        signal_records = []
        for _, row in result.iterrows():
            for factor in active_factors:
                signal_records.append({
                    "ticker": row["ticker"],
                    "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "model_id": model.name,
                    "run_id": run_id,
                    "factor_name": factor.name,
                    "raw_value": factor_data[factor.name].get(row["ticker"]),
                    "normalized_value": row.get(factor.name),
                    "composite_score": row["composite_score"],
                })
        self.store.save_signals(signal_records)

        return result

    def _get_factor_values(self, tickers: list[str], factor: FactorConfig) -> pd.Series | None:
        if factor.type == "python" and factor.module:
            return self._get_custom_factor(tickers, factor)

        if factor.metric is None:
            return None

        if factor.metric not in METRIC_SOURCES:
            logger.warning("Unknown metric: %s", factor.metric)
            return None

        table, column = METRIC_SOURCES[factor.metric]
        placeholders = ",".join("?" for _ in tickers)
        query = f"SELECT ticker, {column} FROM {table} WHERE ticker IN ({placeholders})"

        # For fundamentals, get most recent quarter
        if table == "fundamentals":
            query = (
                f"SELECT ticker, {column} FROM {table} "
                f"WHERE ticker IN ({placeholders}) "
                f"GROUP BY ticker HAVING quarter = MAX(quarter)"
            )

        df = pd.read_sql_query(query, self.store._conn, params=tickers)
        if df.empty:
            return None
        return df.set_index("ticker")[column]

    def _get_custom_factor(self, tickers: list[str], factor: FactorConfig) -> pd.Series | None:
        try:
            mod = importlib.import_module(factor.module)
            compute_fn = getattr(mod, "compute")
            results = {}
            for ticker in tickers:
                prices = self.store.get_prices(ticker)
                try:
                    results[ticker] = compute_fn(ticker, prices)
                except Exception as e:
                    logger.error("Custom factor '%s' failed for %s: %s", factor.name, ticker, e)
            return pd.Series(results) if results else None
        except Exception as e:
            logger.error("Failed to load custom factor module '%s': %s", factor.module, e)
            return None

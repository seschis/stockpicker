from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator


class ScreenConfig(BaseModel):
    name: str
    filters: dict[str, Any]


class FactorConfig(BaseModel):
    name: str
    metric: str | None = None
    weight: float
    direction: Literal["higher_is_better", "lower_is_better"] = "higher_is_better"
    type: Literal["builtin", "python"] = "builtin"
    module: str | None = None

    @field_validator("weight")
    @classmethod
    def weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight must be >= 0")
        return v


class ModelConfig(BaseModel):
    name: str
    factors: list[FactorConfig]

    @model_validator(mode="after")
    def check_weights(self) -> ModelConfig:
        total = sum(f.weight for f in self.factors)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Factor weights must sum to 1.0, got {total:.4f}")
        return self


class BuyRules(BaseModel):
    top_n: int = 10
    position_size: Literal["equal", "score_weighted"] = "equal"

    @field_validator("top_n")
    @classmethod
    def top_n_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("top_n must be >= 1")
        return v


class SellRules(BaseModel):
    hold_days: int = 30
    stop_loss: float = -0.08

    @field_validator("hold_days")
    @classmethod
    def hold_days_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("hold_days must be >= 1")
        return v

    @model_validator(mode="after")
    def check_stop_loss(self) -> SellRules:
        if self.stop_loss >= 0:
            raise ValueError("stop_loss must be negative")
        return self


class PortfolioRules(BaseModel):
    initial_capital: float = 100_000.0
    max_positions: int = 10
    max_position_pct: float = 0.15

    @field_validator("max_positions")
    @classmethod
    def max_positions_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_positions must be >= 1")
        return v

    @model_validator(mode="after")
    def check_pct(self) -> PortfolioRules:
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be between 0 and 1")
        return self


class CostRules(BaseModel):
    commission_per_trade: float = 0.0
    slippage_bps: float = 5.0


class StrategyRules(BaseModel):
    buy: BuyRules = BuyRules()
    sell: SellRules = SellRules()
    portfolio: PortfolioRules = PortfolioRules()
    costs: CostRules = CostRules()


class StrategyConfig(BaseModel):
    name: str
    screen: str
    model: str
    rules: StrategyRules

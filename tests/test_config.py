import pytest
from pydantic import ValidationError

from stockpicker.config.models import (
    ScreenConfig, FactorConfig, ModelConfig, StrategyConfig,
    BuyRules, SellRules, PortfolioRules,
)


def test_screen_config_valid():
    cfg = ScreenConfig(
        name="US Mid-Cap Tech",
        filters={"market_cap": [2_000_000_000, 10_000_000_000], "sector": ["Technology"]},
    )
    assert cfg.name == "US Mid-Cap Tech"


def test_model_config_weights_must_sum_to_one():
    with pytest.raises(ValidationError, match="weights must sum to 1.0"):
        ModelConfig(
            name="bad-model",
            factors=[
                FactorConfig(name="value", metric="pe_ratio", weight=0.5, direction="lower_is_better"),
                FactorConfig(name="growth", metric="revenue_growth_yoy", weight=0.3, direction="higher_is_better"),
            ],
        )


def test_model_config_valid():
    cfg = ModelConfig(
        name="good-model",
        factors=[
            FactorConfig(name="value", metric="pe_ratio", weight=0.6, direction="lower_is_better"),
            FactorConfig(name="growth", metric="revenue_growth_yoy", weight=0.4, direction="higher_is_better"),
        ],
    )
    assert len(cfg.factors) == 2


def test_strategy_config_stop_loss_must_be_negative():
    with pytest.raises(ValidationError):
        StrategyConfig(
            name="bad",
            screen="test",
            model="test",
            rules={
                "buy": {"top_n": 10, "position_size": "equal"},
                "sell": {"hold_days": 30, "stop_loss": 0.08},
                "portfolio": {"initial_capital": 100000, "max_positions": 10, "max_position_pct": 0.15},
                "costs": {"commission_per_trade": 0.0, "slippage_bps": 5},
            },
        )


def test_buy_rules_top_n_must_be_positive():
    with pytest.raises(ValidationError):
        BuyRules(top_n=0)


def test_sell_rules_hold_days_must_be_positive():
    with pytest.raises(ValidationError):
        SellRules(hold_days=0)


def test_portfolio_max_positions_must_be_positive():
    with pytest.raises(ValidationError):
        PortfolioRules(max_positions=0)


def test_factor_weight_must_be_non_negative():
    with pytest.raises(ValidationError):
        FactorConfig(name="test", weight=-0.5)


from pathlib import Path
from stockpicker.config.loader import load_screen, load_model


def test_load_screen_from_yaml(tmp_path: Path):
    yaml_content = """
name: Test Screen
filters:
  market_cap: [1000000000, 5000000000]
  sector: [Technology]
"""
    p = tmp_path / "screen.yaml"
    p.write_text(yaml_content)
    cfg = load_screen(p)
    assert cfg.name == "Test Screen"


def test_load_model_from_yaml(tmp_path: Path):
    yaml_content = """
name: test-model
factors:
  - name: value
    metric: pe_ratio
    weight: 0.5
    direction: lower_is_better
  - name: growth
    metric: revenue_growth_yoy
    weight: 0.5
    direction: higher_is_better
"""
    p = tmp_path / "model.yaml"
    p.write_text(yaml_content)
    cfg = load_model(p)
    assert cfg.name == "test-model"
    assert len(cfg.factors) == 2

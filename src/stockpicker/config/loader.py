import logging
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from stockpicker.config.models import ModelConfig, ScreenConfig, StrategyConfig

logger = logging.getLogger("stockpicker.config")

T = TypeVar("T", bound=BaseModel)


def load_yaml(path: Path, config_type: type[T]) -> T:
    logger.debug("Loading config from %s", path)
    with open(path) as f:
        data = yaml.safe_load(f)
    return config_type.model_validate(data)


def load_screen(path: Path) -> ScreenConfig:
    return load_yaml(path, ScreenConfig)


def load_model(path: Path) -> ModelConfig:
    return load_yaml(path, ModelConfig)


def load_strategy(path: Path) -> StrategyConfig:
    return load_yaml(path, StrategyConfig)

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

from stockpicker.config.models import ModelConfig, ScreenConfig, StrategyConfig

logger = logging.getLogger("stockpicker.config")


def load_yaml[T: BaseModel](path: Path, config_type: type[T]) -> T:
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

import logging
import sys
from pathlib import Path

LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


def setup_logging(verbosity: int = 0, log_dir: Path | None = None) -> None:
    level = LEVELS.get(verbosity, logging.DEBUG)
    logger = logging.getLogger("stockpicker")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(fmt)
    logger.addHandler(stderr_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_dir / "stockpicker.log", maxBytes=5_000_000, backupCount=3
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

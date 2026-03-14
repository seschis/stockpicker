from stockpicker.logging_config import setup_logging
import logging


def test_setup_logging_default_level():
    setup_logging(verbosity=0)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.WARNING


def test_setup_logging_verbose():
    setup_logging(verbosity=1)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.INFO


def test_setup_logging_very_verbose():
    setup_logging(verbosity=2)
    logger = logging.getLogger("stockpicker")
    assert logger.level == logging.DEBUG

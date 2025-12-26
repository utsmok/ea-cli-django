"""
Loguru logging configuration for Easy Access Platform.

Intercepts stdlib logging and redirects to loguru for consistent formatting.
"""

import logging
import os
import sys
from pathlib import Path

from loguru import logger

# Remove default loguru handler
logger.remove()

# Determine log level from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if os.getenv("DEBUG") else "INFO")

# Console handler with colors
logger.add(
    sys.stdout,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level=LOG_LEVEL,
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# File handler for production (only in non-DEBUG mode)
if not os.getenv("DEBUG"):
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    logger.add(
        logs_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        enqueue=True,
    )


class InterceptHandler(logging.Handler):
    """Intercept stdlib logging and redirect to loguru."""

    def emit(self, record):
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging():
    """Configure loguru to intercept all stdlib logging."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercept Django loggers
    for logger_name in ["django", "django.request", "django.db.backends"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False


# Auto-setup when module is imported
setup_logging()

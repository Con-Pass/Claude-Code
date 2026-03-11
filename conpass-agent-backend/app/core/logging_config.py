"""Centralized logging configuration for the application."""

import logging
import sys
from typing import Optional
import os

ENV_LOG_LEVELS = {
    "test": logging.INFO,
    "staging": logging.INFO,
    "production": logging.INFO,
}


def setup_logging(
    env: Optional[str] = None, format_string: Optional[str] = None
) -> None:
    """
    Set up centralized logging configuration for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string. If None, uses default format.
    """

    if env is None:
        env = os.getenv("ENVIRONMENT", "test")

    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

    level = ENV_LOG_LEVELS.get(env.lower(), logging.INFO)
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Set specific loggers to appropriate levels
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(
        logging.INFO if env == "test" else logging.WARNING
    )
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("fastapi").setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the application's standard configuration.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

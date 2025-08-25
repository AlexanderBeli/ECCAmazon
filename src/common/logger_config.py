# src/common/logger_config.py
"""Application-wide logging configuration."""

import logging

from src.common.config.settings import settings  # Import settings for log level


def setup_logging() -> None:
    """Configures basic logging for the application."""
    log_level_str = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()  # Output logs to console
            # logging.FileHandler("app.log") # Optionally, add file output
        ],
    )
    # Suppress verbose logging from libraries
    logging.getLogger("mysql.connector").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

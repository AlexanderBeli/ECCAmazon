# src/common/logger_config.py
"""Application-wide logging configuration."""

import logging

from rich.logging import RichHandler

from src.common.config.settings import settings  # Import settings for log level


def setup_logging() -> None:
    """Configures basic logging for the application."""
    log_level_str = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # logging.basicConfig(
    #     level=log_level,
    #     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    #     handlers=[
    #         logging.StreamHandler()  # Output logs to console
    #         # logging.FileHandler("app.log") # Optionally, add file output
    #     ],
    # )

    # Rich settings
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    rich_handler = RichHandler(
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
        tracebacks_word_wrap=True,
        tracebacks_suppress=[
            logging,
        ],
    )

    root_logger.addHandler(rich_handler)

    if len(root_logger.handlers) > 1:
        root_logger.handlers = [rich_handler]

    # Suppress verbose logging from libraries
    logging.getLogger("mysql.connector").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

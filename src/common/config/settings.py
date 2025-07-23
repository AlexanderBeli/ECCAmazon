"""Application settings and environment variables."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_DATABASE: str = os.getenv("DB_NAME", "product_data_db")  # Renamed for clarity across projects
    DB_USER: str = os.getenv("DB_USER", "user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")

    ECC_API_BASE_URL: str = os.getenv("ECC_API_BASE_URL")
    ECC_API_TOKEN: str = os.getenv("ECC_API_TOKEN")

    EAN_AVAILABILITY_API_BASE_URL: str = os.getenv("EAN_AVAILABILITY_API_BASE_URL")
    EAN_AVAILABILITY_API_TOKEN: Optional[str] = os.getenv("EAN_AVAILABILITY_API_TOKEN")

    RETAILER_ID: str = os.getenv("RETAILER_ID", "default_retailer_id")
    RETAILER_GLN: str = os.getenv("RETAILER_GLN", "default_retailer_gln")

    AMAZON_API_KEY: Optional[str] = os.getenv("AMAZON_API_KEY")
    EBAY_CLIENT_ID: Optional[str] = os.getenv("EBAY_CLIENT_ID")
    # Add other marketplace specific settings here

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # INFO, DEBUG, WARNING, ERROR, CRITICAL


settings = Settings()

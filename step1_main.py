"""Main application entry point for GTIN Stock synchronization."""

import schedule
import time
import pytz
from datetime import datetime
import os

from src.common.config.settings import settings
from src.common.exceptions.custom_exceptions import APIError, DatabaseError, ApplicationError

# Product Availability Domain Imports (GTIN Stock)
from src.product_availability_domain.application.gtin_stock_service import GtinStockApplicationService
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient
from src.common.dtos.availability_dtos import SupplierContextDTO  # Import for direct use in main for display

# Define the path to the suppliers JSON configuration file
SUPPLIERS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "common", "config", "suppliers.json")


def setup_gtin_stock_dependencies() -> GtinStockApplicationService:
    """Initializes and wires up GTIN Stock domain dependencies."""
    global_stock_api_client = GlobalStockApiClient()
    gtin_stock_repository = MySQLGtinStockRepository()
    gtin_stock_app_service = GtinStockApplicationService(
        stock_repo=gtin_stock_repository, api_client=global_stock_api_client
    )
    return gtin_stock_app_service


def create_gtin_stock_db_tables() -> None:
    """Creates tables for the GTIN Stock domain."""
    gtin_stock_repo = MySQLGtinStockRepository()
    try:
        gtin_stock_repo.create_tables()
    except DatabaseError as e:
        print(f"Error creating GTIN Stock database tables: {e}")
        # Consider exiting or raising if table creation is critical and failed
    finally:
        # Ensure connection is closed if not managed by a connection pool
        del gtin_stock_repo


def run_gtin_stock_sync_process() -> None:
    """
    Runs the GTIN Stock synchronization process for all configured suppliers.
    This function will be scheduled to run daily.
    """
    print(f"\n--- Starting GTIN Stock Synchronization at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    create_gtin_stock_db_tables()  # Ensure tables exist each run (idempotent)
    gtin_stock_app_service = setup_gtin_stock_dependencies()

    try:
        gtin_stock_app_service.sync_all_supplier_stock(SUPPLIERS_CONFIG_PATH)

        # Example of fetching the saved data for one supplier after sync
        print("\n--- Fetching recently synced GTIN Stock from DB (Example: Josef Seibel) ---")
        # You'd typically load this context from the suppliers.json or a specific query
        example_supplier_context = SupplierContextDTO(
            retailer_id=settings.RETAILER_ID,
            retailer_gln=settings.RETAILER_GLN,
            supplier_id=87,  # Josef Seibel's ID
            supplier_gln="4042834000005",  # Josef Seibel's GLN
            supplier_name="Josef Seibel",
        )
        fetched_stock = gtin_stock_app_service.get_supplier_stock_data(example_supplier_context)

        print(
            f"  Supplier: {fetched_stock.supplier_context.supplier_name} (GLN: {fetched_stock.supplier_context.supplier_gln}), Retailer: {fetched_stock.supplier_context.retailer_id}"
        )
        for item in fetched_stock.stock_items[:5]:  # Print first 5 items as example
            print(
                f"    GTIN: {item.gtin}, Quantity: {item.quantity}, Traffic Light: {item.stock_traffic_light}, Type: {item.item_type}, Timestamp: {item.timestamp}"
            )
        if len(fetched_stock.stock_items) > 5:
            print(f"    ... and {len(fetched_stock.stock_items) - 5} more items.")

    except (APIError, DatabaseError, ApplicationError) as e:
        print(f"An error occurred during GTIN Stock synchronization: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print(f"--- GTIN Stock Synchronization Finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")


if __name__ == "__main__":
    print("Product Data Synchronization Service (GTIN Stock Module) Started.")
    print("Scheduling GTIN Stock sync for every day at 18:00 Germany time.")

    germany_tz = pytz.timezone("Europe/Berlin")

    # Schedule the task
    # schedule.every().day.at("18:00", germany_tz).do(run_gtin_stock_sync_process)

    run_gtin_stock_sync_process()

    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)  # Wait one second before checking again

# main.py
"""Main application entry point for GTIN Stock synchronization with optimizations."""

import json
import logging
import os
import time
from datetime import datetime

import pytz
import schedule

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import GtinStockItemDTO, SupplierContextDTO
from src.common.exceptions.custom_exceptions import (
    APIError,
    ApplicationError,
    DatabaseError,
)
from src.common.logger_config import setup_logging

# Product Availability Domain Imports (GTIN Stock)
from src.product_availability_domain.application.gtin_stock_service import (
    GtinStockApplicationService,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import (
    GlobalStockApiClient,
)
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)

# Define the path to the suppliers JSON configuration file
SUPPLIERS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "common", "config", "suppliers.json")
logger = logging.getLogger(__name__)


def setup_gtin_stock_dependencies() -> tuple[GtinStockApplicationService, MySQLGtinStockRepository]:
    """Initializes and wires up GTIN Stock domain dependencies."""
    global_stock_api_client = GlobalStockApiClient()
    gtin_stock_repository = MySQLGtinStockRepository()
    gtin_stock_app_service = GtinStockApplicationService(
        stock_repo=gtin_stock_repository, api_client=global_stock_api_client
    )
    return gtin_stock_app_service, gtin_stock_repository


def create_gtin_stock_db_tables() -> None:
    """Creates tables for the GTIN Stock domain."""
    gtin_stock_repo = MySQLGtinStockRepository()
    try:
        gtin_stock_repo.create_tables()
        logger.info("✅ Database tables created/verified successfully")
    except DatabaseError as e:
        logger.error(f"❌ Error creating GTIN Stock database tables: {e}")
        raise  # Re-raise if table creation is critical
    finally:
        # Ensure connection is closed if not managed by a connection pool
        del gtin_stock_repo


def load_suppliers_config(config_path: str) -> list[dict]:
    """Loads and validates suppliers configuration from JSON file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            suppliers_data = json.load(f)

        # Handle different JSON structures
        if isinstance(suppliers_data, dict) and "suppliers" in suppliers_data:
            suppliers_list = suppliers_data["suppliers"]
        elif isinstance(suppliers_data, list):
            suppliers_list = suppliers_data
        else:
            raise ApplicationError("Invalid suppliers configuration format")

        if not suppliers_list:
            raise ApplicationError("No suppliers found in configuration")

        return suppliers_list

    except FileNotFoundError:
        raise ApplicationError(f"Suppliers configuration file not found at {config_path}")
    except json.JSONDecodeError as e:
        raise ApplicationError(f"Error decoding suppliers configuration: {e}")


def create_supplier_context(supplier_data: dict) -> SupplierContextDTO:
    """Creates SupplierContextDTO from supplier configuration data."""
    # Handle different possible key formats in the JSON
    supplier_id = supplier_data.get("supplier_id") or supplier_data.get("SUPPLIER_ID")
    supplier_gln = supplier_data.get("supplier_gln") or supplier_data.get("SUPPLIER_GLN")
    supplier_name = supplier_data.get("supplier_name") or supplier_data.get("SUPPLIER_NAME")

    if not all([supplier_id, supplier_gln, supplier_name]):
        raise ApplicationError(f"Missing required supplier fields in config: {supplier_data}")

    return SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=supplier_id,
        supplier_gln=supplier_gln,
        supplier_name=supplier_name,
    )


def run_gtin_stock_sync_process_optimized() -> None:
    """
    Optimized GTIN Stock synchronization process with batch processing and intermediate saves.
    Features:
    - Batch processing (100 GTINs per batch)
    - Intermediate saves after each batch to prevent data loss
    - Sequential processing to respect API rate limits
    - Progress tracking and error handling per supplier
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"🚀 Starting Optimized GTIN Stock Synchronization")
    logger.info(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*80}")

    try:
        # Initialize database and dependencies
        create_gtin_stock_db_tables()
        gtin_stock_app_service, gtin_stock_repository = setup_gtin_stock_dependencies()

        # Load suppliers configuration
        suppliers_list = load_suppliers_config(SUPPLIERS_CONFIG_PATH)
        logger.info(f"📋 Loaded {len(suppliers_list)} suppliers from configuration")

        total_processed_items = 0
        successful_suppliers = 0
        failed_suppliers = 0

        for supplier_index, supplier_data in enumerate(suppliers_list, 1):
            try:
                supplier_context = create_supplier_context(supplier_data)

                logger.info(f"\n{'─'*60}")
                logger.info(
                    f"🏭 Processing supplier {supplier_index}/{len(suppliers_list)}: {supplier_context.supplier_name}"
                )
                logger.info(f"   GLN: {supplier_context.supplier_gln}")
                logger.info(f"{'─'*60}")

                # Define batch save callback for intermediate saves
                def batch_save_callback(context: SupplierContextDTO, items: list[GtinStockItemDTO]) -> None:
                    """Callback to save batches immediately for data persistence and fault tolerance."""
                    if items:
                        gtin_stock_repository.batch_save_gtin_stock_items(context, items)

                # Use optimized API client with batch processing and intermediate saves
                stock_response = gtin_stock_app_service.api_client.fetch_gtin_stock_data_optimized(
                    supplier_context=supplier_context,
                    batch_size=100,  # Process 100 GTINs at a time for optimal performance
                    max_workers=1,  # Sequential processing to respect API rate limits
                    save_callback=batch_save_callback,  # Save each batch immediately
                )

                supplier_items_count = len(stock_response.stock_items)
                total_processed_items += supplier_items_count
                successful_suppliers += 1

                logger.info(f"✅ Completed {supplier_context.supplier_name}: {supplier_items_count} items processed")

            except Exception as e:  # noqa: PERF203
                failed_suppliers += 1
                logger.error(f"❌ Failed to process supplier {supplier_data.get('supplier_name', 'Unknown')}: {e}")
                # Continue with next supplier even if one fails
                continue

        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 SYNCHRONIZATION SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"✅ Successful suppliers: {successful_suppliers}")
        logger.info(f"❌ Failed suppliers: {failed_suppliers}")
        logger.info(f"📦 Total items processed: {total_processed_items}")
        logger.info(f"⏱️  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")

        # Example: Display some data from database for verification
        if successful_suppliers > 0:
            display_sample_data(gtin_stock_app_service)

    except Exception as e:
        logger.error(f"💥 Critical error during synchronization: {e}")
        raise


def display_sample_data(gtin_stock_app_service: GtinStockApplicationService) -> None:
    """Displays sample data from database for verification after sync."""
    try:
        logger.info(f"\n{'─'*60}")
        logger.info(f"🔍 SAMPLE DATA VERIFICATION")
        logger.info(f"{'─'*60}")

        # Get all unique supplier GLNs
        supplier_glns = gtin_stock_app_service.get_unique_supplier_glns()
        if supplier_glns:
            sample_gln = supplier_glns[0]

            # Create a sample context for the first supplier
            sample_context = SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=1,  # Placeholder ID
                supplier_gln=sample_gln,
                supplier_name="Sample Verification",
            )

            fetched_stock = gtin_stock_app_service.get_supplier_stock_data(sample_context)

            logger.info(f"📋 Sample from GLN: {sample_gln}")
            logger.info(f"📦 Total items for this supplier: {len(fetched_stock.stock_items)}")

            # Display first 3 items as sample
            for i, item in enumerate(fetched_stock.stock_items[:3], 1):
                logger.info(f"   {i}. GTIN: {item.gtin}")
                logger.info(f"      Quantity: {item.quantity}")
                logger.info(f"      Traffic Light: {item.stock_traffic_light}")
                logger.info(f"      Type: {item.item_type}")
                logger.info(f"      Timestamp: {item.timestamp}")
                logger.info()

            if len(fetched_stock.stock_items) > 3:
                logger.info(f"   ... and {len(fetched_stock.stock_items) - 3} more items")

        # Display overall statistics
        total_gtins = len(gtin_stock_app_service.get_all_gtin_codes())
        total_suppliers = len(gtin_stock_app_service.get_unique_supplier_glns())

        logger.info(f"📊 DATABASE STATISTICS:")
        logger.info(f"   Total unique GTINs: {total_gtins}")
        logger.info(f"   Total suppliers: {total_suppliers}")

    except Exception as e:
        logger.error(f"⚠️  Error displaying sample data: {e}")


def run_legacy_sync_process() -> None:
    """
    Legacy synchronization process (kept for backward compatibility).
    Uses the original sync_all_supplier_stock method.
    """
    logger.info(
        f"\n--- Starting Legacy GTIN Stock Synchronization at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---"
    )

    create_gtin_stock_db_tables()
    gtin_stock_app_service, _ = setup_gtin_stock_dependencies()

    try:
        gtin_stock_app_service.sync_all_supplier_stock(SUPPLIERS_CONFIG_PATH)

        # Example of fetching saved data
        logger.info("\n--- Sample Data Verification ---")
        supplier_glns = gtin_stock_app_service.get_unique_supplier_glns()
        if supplier_glns:
            example_supplier_context = SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=1,  # Placeholder
                supplier_gln=supplier_glns[0],
                supplier_name="Sample",
            )
            fetched_stock = gtin_stock_app_service.get_supplier_stock_data(example_supplier_context)

            logger.info(f"Sample GLN: {supplier_glns[0]}, Items: {len(fetched_stock.stock_items)}")
            for item in fetched_stock.stock_items[:3]:
                logger.info(f"  GTIN: {item.gtin}, Qty: {item.quantity}, Light: {item.stock_traffic_light}")

    except (APIError, DatabaseError, ApplicationError) as e:
        logger.error(f"An error occurred during GTIN Stock synchronization: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

    logger.info(f"--- GTIN Stock Synchronization Finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")


if __name__ == "__main__":
    setup_logging()
    logger.info("🎯 Product Data Synchronization Service (GTIN Stock Module)")
    logger.info("📅 Scheduling GTIN Stock sync for every day at 18:00 Germany time")

    germany_tz = pytz.timezone("Europe/Berlin")

    # Schedule the optimized task
    schedule.every().day.at("18:00", germany_tz).do(run_gtin_stock_sync_process_optimized)

    # For immediate testing, run the optimized process once
    logger.info("🔄 Running immediate sync for testing...")
    run_gtin_stock_sync_process_optimized()

    # Uncomment below for scheduled execution
    logger.info("⏰ Scheduler started. Waiting for scheduled time...")
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds instead of every second

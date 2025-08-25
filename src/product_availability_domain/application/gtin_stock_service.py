# src/product_availability_domain/application/gtin_stock_service.py
"""Application service for GTIN Stock synchronization with batch processing support."""

import json
import logging

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.common.exceptions.custom_exceptions import ApplicationError
from src.product_availability_domain.domain.repositories.gtin_stock_repository import (
    IGtinStockRepository,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import (
    GlobalStockApiClient,
)

logger = logging.getLogger(__name__)


class GtinStockApplicationService:
    """Service for synchronizing and managing GTIN stock data with optimizations."""

    def __init__(self, stock_repo: IGtinStockRepository, api_client: GlobalStockApiClient) -> None:
        """Initializes the GtinStockApplicationService."""
        self.stock_repo = stock_repo
        self.api_client = api_client

    def sync_all_supplier_stock(self, suppliers_config_path: str) -> None:
        """
        Legacy method: Orchestrates fetching GTIN stock data from the Global Stock API
        for all configured suppliers and saves it to the database.

        Note: This method loads all data before saving. For large datasets,
        consider using sync_all_supplier_stock_optimized instead.
        """
        logger.info(f"Starting GTIN stock synchronization for all configured suppliers...")

        try:
            with open(suppliers_config_path, "r", encoding="utf-8") as f:
                suppliers_data = json.load(f)
        except FileNotFoundError:
            raise ApplicationError(f"Suppliers configuration file not found at {suppliers_config_path}")
        except json.JSONDecodeError:
            raise ApplicationError(f"Error decoding suppliers configuration from {suppliers_config_path}")

        # Handle different JSON structures
        if isinstance(suppliers_data, dict) and "suppliers" in suppliers_data:
            suppliers_list = suppliers_data["suppliers"]
        elif isinstance(suppliers_data, list):
            suppliers_list = suppliers_data
        else:
            raise ApplicationError("Invalid suppliers configuration format")

        for supplier_info in suppliers_list:
            # Handle different key formats
            supplier_id = supplier_info.get("supplier_id") or supplier_info.get("SUPPLIER_ID")
            supplier_gln = supplier_info.get("supplier_gln") or supplier_info.get("SUPPLIER_GLN")
            supplier_name = supplier_info.get("supplier_name") or supplier_info.get("SUPPLIER_NAME")

            supplier_context = SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=supplier_id,
                supplier_gln=supplier_gln,
                supplier_name=supplier_name,
            )

            logger.info(
                f"\n--- Processing supplier: {supplier_context.supplier_name} (GLN: {supplier_context.supplier_gln}) ---"
            )

            try:
                # Use legacy method that loads all data first
                stock_response_dto = self.api_client.fetch_gtin_stock_data(supplier_context)

                if not stock_response_dto or not stock_response_dto.stock_items:
                    logger.warning(f"No GTIN stock data received from API for {supplier_context.supplier_name}.")
                    continue

                # Save all items in a single batch for better performance
                self.stock_repo.batch_save_gtin_stock_items(supplier_context, stock_response_dto.stock_items)

                logger.info(
                    f"GTIN stock synchronization completed for {len(stock_response_dto.stock_items)} items for {supplier_context.supplier_name}."
                )

            except Exception as e:
                logger.error(f"Error syncing stock for {supplier_context.supplier_name}: {e}")
                logger.error(f"An error occurred while syncing stock for {supplier_context.supplier_name}: {e}")
                # Continue with next supplier even if one fails
                continue

        logger.info("GTIN stock synchronization for all suppliers finished.")

    def sync_all_supplier_stock_optimized(self, suppliers_config_path: str, batch_size: int = 100) -> None:
        """
        Optimized version: Orchestrates fetching GTIN stock data with batch processing
        and intermediate saves for better performance and fault tolerance.

        Args:
            suppliers_config_path: Path to suppliers configuration JSON
            batch_size: Number of GTINs to process in each batch
        """
        logger.info(f"Starting optimized GTIN stock synchronization for all configured suppliers...")

        try:
            with open(suppliers_config_path, "r", encoding="utf-8") as f:
                suppliers_data = json.load(f)
        except FileNotFoundError:
            raise ApplicationError(f"Suppliers configuration file not found at {suppliers_config_path}")
        except json.JSONDecodeError:
            raise ApplicationError(f"Error decoding suppliers configuration from {suppliers_config_path}")

        # Handle different JSON structures
        if isinstance(suppliers_data, dict) and "suppliers" in suppliers_data:
            suppliers_list = suppliers_data["suppliers"]
        elif isinstance(suppliers_data, list):
            suppliers_list = suppliers_data
        else:
            raise ApplicationError("Invalid suppliers configuration format")

        for supplier_info in suppliers_list:
            # Handle different key formats
            supplier_id = supplier_info.get("supplier_id") or supplier_info.get("SUPPLIER_ID")
            supplier_gln = supplier_info.get("supplier_gln") or supplier_info.get("SUPPLIER_GLN")
            supplier_name = supplier_info.get("supplier_name") or supplier_info.get("SUPPLIER_NAME")

            supplier_context = SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=supplier_id,
                supplier_gln=supplier_gln,
                supplier_name=supplier_name,
            )

            logger.info(
                f"\n--- Processing supplier: {supplier_context.supplier_name} (GLN: {supplier_context.supplier_gln}) ---"
            )

            try:
                # Define callback for batch saving
                def batch_save_callback(context: SupplierContextDTO, items: list[GtinStockItemDTO]) -> None:
                    """Callback to save batches immediately."""
                    if items:
                        self.stock_repo.batch_save_gtin_stock_items(context, items)

                # Use optimized API client with batch processing
                stock_response_dto = self.api_client.fetch_gtin_stock_data_optimized(
                    supplier_context=supplier_context,
                    batch_size=batch_size,
                    max_workers=1,  # Sequential processing to respect API limits
                    save_callback=batch_save_callback,
                )

                logger.info(
                    f"Optimized GTIN stock synchronization completed for {len(stock_response_dto.stock_items)} items for {supplier_context.supplier_name}."
                )

            except Exception as e:
                logger.error(f"Error syncing stock for {supplier_context.supplier_name}: {e}")
                logger.error(f"An error occurred while syncing stock for {supplier_context.supplier_name}: {e}")
                # Continue with next supplier even if one fails
                continue

        logger.info("Optimized GTIN stock synchronization for all suppliers finished.")

    def sync_supplier_stock_with_callback(
        self, supplier_context: SupplierContextDTO, batch_size: int = 100, progress_callback: callable = None
    ) -> GtinStockResponseDTO:
        """
        Syncs stock for a single supplier with optional progress callback.

        Args:
            supplier_context: Supplier context information
            batch_size: Number of GTINs to process in each batch
            progress_callback: Optional callback function for progress tracking

        Returns:
            GtinStockResponseDTO with all processed items
        """
        logger.info(f"Starting stock sync for supplier: {supplier_context.supplier_name}")

        # Define batch save callback
        def batch_save_callback(context: SupplierContextDTO, items: list[GtinStockItemDTO]) -> None:
            """Saves batch and calls progress callback if provided."""
            if items:
                self.stock_repo.batch_save_gtin_stock_items(context, items)
                if progress_callback:
                    progress_callback(context, len(items))

        # Use optimized API client
        return self.api_client.fetch_gtin_stock_data_optimized(
            supplier_context=supplier_context, batch_size=batch_size, max_workers=1, save_callback=batch_save_callback
        )

    def get_supplier_stock_data(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves GTIN stock data for a specific supplier context from the database."""
        return self.stock_repo.get_gtin_stock_by_supplier_context(supplier_context)

    def get_gtin_stock_by_gtin_and_supplier(self, gtin: str, supplier_gln: str) -> GtinStockItemDTO:
        """Retrieves a specific GTIN stock item by GTIN and supplier GLN."""
        return self.stock_repo.get_gtin_stock_by_gtin_and_supplier(gtin, supplier_gln)

    def get_all_gtin_codes(self) -> list[str]:
        """Retrieves all unique GTIN codes from stock table."""
        return self.stock_repo.get_all_gtin_codes()

    def get_unique_supplier_glns(self) -> list[str]:
        """Retrieves all unique supplier GLNs from stock table."""
        return self.stock_repo.get_unique_supplier_glns()

    def get_all_supplier_gtin_pairs(self) -> list[tuple[str, str]]:
        """Retrieves all unique supplier_gln and gtin pairs."""
        return self.stock_repo.get_all_supplier_gtin_pairs()

    def check_existing_gtin_supplier_pairs(self, gtin_supplier_pairs: list[tuple[str, str]]) -> set[tuple[str, str]]:
        """Checks which GTIN-Supplier pairs already exist in the database."""
        return self.stock_repo.check_existing_gtin_supplier_pairs(gtin_supplier_pairs)

    def get_stock_statistics(self) -> dict:
        """Returns statistics about the stock data."""
        total_gtins = len(self.get_all_gtin_codes())
        total_suppliers = len(self.get_unique_supplier_glns())
        total_pairs = len(self.get_all_supplier_gtin_pairs())

        return {
            "total_unique_gtins": total_gtins,
            "total_suppliers": total_suppliers,
            "total_gtin_supplier_pairs": total_pairs,
            "average_gtins_per_supplier": round(total_pairs / total_suppliers, 2) if total_suppliers > 0 else 0,
        }

"""Application service for GTIN Stock synchronization."""

import json
import logging
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO
from src.product_availability_domain.domain.repositories.gtin_stock_repository import IGtinStockRepository
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient
from src.common.config.settings import settings  # For RETAILER_ID/GLN
from src.common.exceptions.custom_exceptions import ApplicationError  # Example for a new exception type

logger = logging.getLogger(__name__)

class GtinStockApplicationService:
    """Service for synchronizing and managing GTIN stock data."""
    def __init__(self, stock_repo: IGtinStockRepository, api_client: GlobalStockApiClient) -> None:
        """Initializes the GtinStockApplicationService."""
        self.stock_repo = stock_repo
        self.api_client = api_client

    def sync_all_supplier_stock(self, suppliers_config_path: str) -> None:
        """
        Orchestrates fetching GTIN stock data from the Global Stock API
        for all configured suppliers and saves it to the database.
        """
        print(f"Starting GTIN stock synchronization for all configured suppliers...")

        try:
            with open(suppliers_config_path, "r") as f:
                suppliers_data = json.load(f)
        except FileNotFoundError:
            raise ApplicationError(f"Suppliers configuration file not found at {suppliers_config_path}")
        except json.JSONDecodeError:
            raise ApplicationError(f"Error decoding suppliers configuration from {suppliers_config_path}")

        for supplier_info in suppliers_data:
            supplier_context = SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=supplier_info["SUPPLIER_ID"],
                supplier_gln=supplier_info["SUPPLIER_GLN"],
                supplier_name=supplier_info["SUPPLIER_NAME"],
            )
            print(
                f"\n--- Processing supplier: {supplier_context.supplier_name} (GLN: {supplier_context.supplier_gln}) ---"
            )

            try:
                stock_response_dto = self.api_client.fetch_gtin_stock_data(supplier_context)

                if not stock_response_dto or not stock_response_dto.stock_items:
                    print(f"No GTIN stock data received from API for {supplier_context.supplier_name}.")
                    continue

                for item_dto in stock_response_dto.stock_items:
                    self.stock_repo.save_gtin_stock_item(supplier_context, item_dto)

                print(
                    f"GTIN stock synchronization completed for {len(stock_response_dto.stock_items)} items for {supplier_context.supplier_name}."
                )

            except Exception as e:
                print(f"An error occurred while syncing stock for {supplier_context.supplier_name}: {e}")
                # Continue with next supplier even if one fails

        print("GTIN stock synchronization for all suppliers finished.")

    def get_supplier_stock_data(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves GTIN stock data for a specific supplier context from the database."""
        return self.stock_repo.get_gtin_stock_by_supplier_context(supplier_context)

"""Application service for EAN/GTIN availability synchronization."""

from src.common.dtos.availability_dtos import EANAvailabilityResponseDTO, SupplierRequestDTO
from src.product_availability_domain.domain.repositories.ean_availability_repository import IEANAvailabilityRepository
from src.product_availability_domain.infrastructure.api_clients.ean_availability_api_client import (
    EANAvailabilityApiClient,
)


class EANAvailabilityApplicationService:
    def __init__(self, availability_repo: IEANAvailabilityRepository, api_client: EANAvailabilityApiClient):
        self.availability_repo = availability_repo
        self.api_client = api_client

    def sync_ean_availability(self, request_dto: SupplierRequestDTO, eans_to_fetch: list[str]):
        """
        Fetches EAN availability and pricing data from an external API
        and saves it to the database for a given supplier context.
        """
        print(
            f"Synchronizing EAN availability for Supplier GLN: {request_dto.supplier_gln}, Retailer ID: {request_dto.retailer_id}...",
        )

        # Hypothetically, the API client takes the request context and EANs
        availability_response_dto = self.api_client.fetch_ean_availability(request_dto, eans_to_fetch)

        if not availability_response_dto or not availability_response_dto.availability_items:
            print("No EAN availability data received from API for synchronization.")
            return

        for item_dto in availability_response_dto.availability_items:
            # The repository will save the EAN availability item along with the supplier context
            self.availability_repo.save_ean_availability_item(request_dto, item_dto)

        print(
            f"EAN availability synchronization completed for {len(availability_response_dto.availability_items)} items.",
        )

    def get_ean_availabilities_by_supplier(self, supplier_gln: str) -> list[EANAvailabilityResponseDTO]:
        """Retrieves all EAN availabilities associated with a specific supplier GLN."""
        return self.availability_repo.get_ean_availabilities_by_supplier(supplier_gln)

    # Future methods for subsequent stages can be added here
    # e.g., def process_price_changes(self):
    # e.g., def update_stock_levels_in_marketplace(self):

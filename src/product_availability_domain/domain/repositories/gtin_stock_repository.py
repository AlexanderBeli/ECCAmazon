"""GTIN (EAN) Availability repository interface."""

from abc import ABC, abstractmethod
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO

# If you decide to map DTOs to domain entities within the application service,
# then this repository would work with EANAvailability entities. For simplicity,
# we can let it work directly with DTOs for now.


class IGtinStockRepository(ABC):
    @abstractmethod
    def save_gtin_stock_item(self, supplier_context: SupplierContextDTO, item: GtinStockItemDTO) -> None:
        """Saves or updates a single GTIN stock item with its supplier context."""
        pass

    @abstractmethod
    def get_gtin_stock_by_supplier_context(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves all GTIN stock for a given supplier and retailer context."""
        pass

    @abstractmethod
    def get_gtin_stock_by_gtin_and_supplier(self, gtin: str, supplier_gln: str) -> GtinStockItemDTO | None:
        """Retrieves a specific GTIN stock item by GTIN and supplier GLN."""
        pass

    @abstractmethod
    def get_all_gtin_codes(self) -> list[str]:
        """Retrieves all unique GTIN codes from stock table."""
        pass

    @abstractmethod
    def get_unique_supplier_glns(self) -> list[str]:
        """Retrieves all unique supplier GLNs from stock table."""
        pass

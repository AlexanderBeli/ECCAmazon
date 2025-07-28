# src/product_availability_domain/domain/repositories/gtin_stock_repository
"""GTIN (EAN) Availability repository interface."""
from abc import ABC, abstractmethod
from typing import Optional

from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)


class IGtinStockRepository(ABC):

    @abstractmethod
    def save_gtin_stock_item(self, supplier_context: SupplierContextDTO, item: GtinStockItemDTO) -> None:
        """Saves or updates a single GTIN stock item with its supplier context."""
        pass

    @abstractmethod
    def batch_save_gtin_stock_items(self, supplier_context: SupplierContextDTO, items: list[GtinStockItemDTO]) -> None:
        """Batch saves multiple GTIN stock items for better performance."""
        pass

    @abstractmethod
    def check_existing_gtin_supplier_pairs(self, gtin_supplier_pairs: list[tuple[str, str]]) -> set[tuple[str, str]]:
        """Checks which GTIN-Supplier pairs already exist in the database."""
        pass

    @abstractmethod
    def get_gtin_stock_by_supplier_context(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves all GTIN stock for a given supplier context."""
        pass

    @abstractmethod
    def get_gtin_stock_by_gtin_and_supplier(self, gtin: str, supplier_gln: str) -> Optional[GtinStockItemDTO]:
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

    @abstractmethod
    def get_all_supplier_gtin_pairs(self) -> list[tuple[str, str]]:
        """Retrieves all unique supplier_gln and gtin pairs."""
        pass

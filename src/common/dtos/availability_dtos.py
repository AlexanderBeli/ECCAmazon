"""Data Transfer Objects for Product Availability data."""

from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class SupplierContextDTO:  # Renamed from SupplierRequestDTO for clarity as it's a context, not just a request
    """DTO for supplier identification and retailer context in availability requests."""

    retailer_id: str
    retailer_gln: str  # Added
    supplier_id: int
    supplier_gln: str
    supplier_name: str


@dataclass
class GtinStockItemDTO:
    """DTO for a single GTIN's stock information."""

    gtin: str
    quantity: int | None = None
    stock_traffic_light: str | None = None
    item_type: str | None = None  # Changed from 'type' to avoid keyword conflict
    timestamp: datetime | None = None  # Added for the exact timestamp from API


@dataclass
class GtinStockResponseDTO:  # Renamed from EANAvailabilityResponseDTO
    """DTO for the response containing a list of GTIN stock items for a given supplier context."""

    supplier_context: SupplierContextDTO
    stock_items: list[GtinStockItemDTO] = field(default_factory=list)

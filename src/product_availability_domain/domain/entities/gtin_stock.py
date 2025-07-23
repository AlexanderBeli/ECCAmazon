"""GTIN Stock entity."""

from dataclasses import dataclass
from datetime import datetime
from .supplier_info import SupplierInfo


@dataclass
class GtinStock:
    """Represents the stock information for a specific GTIN in a supplier context."""

    gtin: str
    supplier_info: SupplierInfo  # Value Object linking to the source
    quantity: int | None = None
    stock_traffic_light: str | None = None
    item_type: str | None = None
    timestamp: datetime | None = None
    id: int | None = None  # For persistence, if it has a unique DB ID

    def __post_init__(self) -> None:
        """Post-initialization for validation."""
        if self.quantity is not None and self.quantity < 0:
            raise ValueError("Quantity cannot be negative.")


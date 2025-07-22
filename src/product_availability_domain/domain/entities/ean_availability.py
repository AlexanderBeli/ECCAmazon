"""EAN Availability entity."""

from dataclasses import dataclass
from typing import Optional

from .supplier_info import SupplierInfo


@dataclass
class EANAvailability:
    """Represents the availability and pricing information for a specific EAN in a supplier context."""

    ean: str
    supplier_info: SupplierInfo  # Value Object linking to the source
    quantity: Optional[int] = None
    price: Optional[float] = None
    # Add other domain-specific fields here, e.g., date_last_updated, status, currency
    id: Optional[int] = None  # For persistence, if it has a unique DB ID

    def __post_init__(self):
        # Example of a simple domain invariant check
        if self.quantity is not None and self.quantity < 0:
            raise ValueError("Quantity cannot be negative.")
        if self.price is not None and self.price < 0:
            raise ValueError("Price cannot be negative.")

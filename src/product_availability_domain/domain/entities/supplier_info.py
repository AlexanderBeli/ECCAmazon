"""Supplier Info value object."""

from dataclasses import dataclass


@dataclass(frozen=True)  # Value objects are immutable
class SupplierInfo:
    """Represents the immutable details of a supplier context for availability data."""

    retailer_id: str
    retailer_gln: str
    supplier_id: str
    supplier_gln: str
    supplier_name: str

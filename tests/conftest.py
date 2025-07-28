# tests/conftest.py
import pytest
from unittest.mock import Mock
from datetime import datetime
import pytz
import json

# Import necessary DTOs and settings
from src.product_availability_domain.application.gtin_stock_service import GtinStockApplicationService
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO
from src.common.config.settings import settings


@pytest.fixture(autouse=True)
def mock_settings_retailer_info(mocker) -> None:
    """Mocks the RETAILER_ID and RETAILER_GLN in settings for consistent testing."""
    mocker.patch.object(settings, "RETAILER_ID", "63153")
    mocker.patch.object(settings, "RETAILER_GLN", "4262543480008")


@pytest.fixture
def mock_gtin_stock_repository() -> Mock:
    """Mock for MySQLGtinStockRepository."""
    # We specify the actual class for a more accurate mock spec
    return Mock(spec=MySQLGtinStockRepository)


@pytest.fixture
def mock_global_stock_api_client() -> Mock:
    """Mock for GlobalStockApiClient."""
    # We specify the actual class for a more accurate mock spec
    return Mock(spec=GlobalStockApiClient)


@pytest.fixture
def gtin_stock_service(mock_gtin_stock_repository, mock_global_stock_api_client) -> GtinStockApplicationService:
    """Instance of GtinStockApplicationService with mocked dependencies."""
    return GtinStockApplicationService(stock_repo=mock_gtin_stock_repository, api_client=mock_global_stock_api_client)


@pytest.fixture
def sample_supplier_context_dto() -> SupplierContextDTO:
    """Sample SupplierContextDTO for tests."""
    # Note: settings are mocked by mock_settings_retailer_info fixture, so these values are consistent
    return SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=87,
        supplier_gln="4042834000005",
        supplier_name="Josef Seibel",
    )


@pytest.fixture
def sample_suppliers_json_data() -> list[dict]:
    """Sample data representing the suppliers.json content."""
    return [
        {"SUPPLIER_ID": 87, "SUPPLIER_NAME": "Josef Seibel", "SUPPLIER_GLN": "4042834000005"},
        {"SUPPLIER_ID": 564, "SUPPLIER_NAME": "Ecco Schuhe GmbH", "SUPPLIER_GLN": "5790000017089"},
    ]


@pytest.fixture
def sample_gtin_stock_item_dto_list() -> list[GtinStockItemDTO]:
    """Sample list of GtinStockItemDTOs."""
    return [
        GtinStockItemDTO(
            gtin="1234567890001",
            quantity=10,
            stock_traffic_light="Green",
            item_type="Pair",
            timestamp=datetime.now(pytz.utc),
        ),
        GtinStockItemDTO(
            gtin="1234567890002",
            quantity=0,
            stock_traffic_light="Red",
            item_type="Pair",
            timestamp=datetime.now(pytz.utc),
        ),
    ]


@pytest.fixture
def sample_gtin_stock_item_dto_list_ecco() -> list[GtinStockItemDTO]:
    """Sample list of GtinStockItemDTOs for Ecco."""
    return [
        GtinStockItemDTO(
            gtin="5790000017001",
            quantity=5,
            stock_traffic_light="Yellow",
            item_type="Pair",
            timestamp=datetime.now(pytz.utc),
        )
    ]


@pytest.fixture
def sample_gtin_stock_item_dto_js() -> GtinStockItemDTO:
    """Sample GtinStockItemDTO for Josef Seibel."""
    return GtinStockItemDTO(
        gtin="1234567890001",
        quantity=10,
        stock_traffic_light="Green",
        item_type="Pair",
        timestamp=datetime.now(pytz.utc),
    )


@pytest.fixture
def sample_gtin_stock_item_dto_ecco() -> GtinStockItemDTO:
    """Sample GtinStockItemDTO for Ecco."""
    return GtinStockItemDTO(
        gtin="5790000017001",
        quantity=5,
        stock_traffic_light="Yellow",
        item_type="Pair",
        timestamp=datetime.now(pytz.utc),
    )

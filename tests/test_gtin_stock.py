"""Tests for the GTIN Stock domain."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import pytz
import json
import requests

# Import necessary classes and DTOs
from src.product_availability_domain.application.gtin_stock_service import GtinStockApplicationService
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO
from src.common.exceptions.custom_exceptions import APIError, DatabaseError, ApplicationError
from src.common.config.settings import settings  # To mock settings.RETAILER_ID/GLN

# --- Fixtures for common test objects ---


@pytest.fixture(autouse=True)  # This fixture will be applied to all tests automatically
def mock_settings_retailer_info(mocker) -> None:
    """Mocks the RETAILER_ID and RETAILER_GLN in settings for consistent testing."""
    mocker.patch.object(settings, "RETAILER_ID", "63153")
    mocker.patch.object(settings, "RETAILER_GLN", "4262543480008")


@pytest.fixture
def mock_gtin_stock_repository() -> Mock:
    """Mock for MySQLGtinStockRepository."""
    return Mock(spec=MySQLGtinStockRepository)


@pytest.fixture
def mock_global_stock_api_client() -> Mock:
    """Mock for GlobalStockApiClient."""
    return Mock(spec=GlobalStockApiClient)


@pytest.fixture
def gtin_stock_service(mock_gtin_stock_repository, mock_global_stock_api_client) -> GtinStockApplicationService:
    """Instance of GtinStockApplicationService with mocked dependencies."""
    return GtinStockApplicationService(stock_repo=mock_gtin_stock_repository, api_client=mock_global_stock_api_client)


@pytest.fixture
def sample_supplier_context_dto() -> SupplierContextDTO:
    """Sample SupplierContextDTO for tests."""
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


# --- Tests for GtinStockApplicationService ---


def test_sync_all_supplier_stock_success(
    gtin_stock_service,
    mock_global_stock_api_client,
    mock_gtin_stock_repository,
    sample_suppliers_json_data,
    mocker,  # Use mocker fixture for patching open/json.load
) -> None:
    """
    Tests successful synchronization of GTIN stock data for multiple suppliers.
    Verifies API client calls and repository save operations.
    """
    # Mock reading the suppliers.json file
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    # Mock the API client's response for a single supplier
    mock_api_response_items = [
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
    # Mock fetch_gtin_stock_data for the first supplier (Josef Seibel)
    mock_global_stock_api_client.fetch_gtin_stock_data.side_effect = [
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=87,
                supplier_gln="4042834000005",
                supplier_name="Josef Seibel",
            ),
            stock_items=mock_api_response_items,
        ),
        # You would add another GtinStockResponseDTO for the second supplier (Ecco) if it were different
        GtinStockResponseDTO(  # For Ecco
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=564,
                supplier_gln="5790000017089",
                supplier_name="Ecco Schuhe GmbH",
            ),
            stock_items=[
                GtinStockItemDTO(
                    gtin="5790000017001",
                    quantity=5,
                    stock_traffic_light="Yellow",
                    item_type="Pair",
                    timestamp=datetime.now(pytz.utc),
                )
            ],
        ),
    ]

    # Execute the service method
    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    # Assertions
    # 1. API client was called for each supplier
    assert mock_global_stock_api_client.fetch_gtin_stock_data.call_count == len(sample_suppliers_json_data)

    # 2. Repository's save method was called for each item of each supplier
    # For Josef Seibel (2 items) + Ecco (1 item) = 3 total save calls
    assert mock_gtin_stock_repository.save_gtin_stock_item.call_count == (len(mock_api_response_items) + 1)

    first_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=87,
        supplier_gln="4042834000005",
        supplier_name="Josef Seibel",
    )
    mock_gtin_stock_repository.save_gtin_stock_item.assert_any_call(first_supplier_context, mock_api_response_items[0])
    mock_gtin_stock_repository.save_gtin_stock_item.assert_any_call(first_supplier_context, mock_api_response_items[1])


def test_sync_all_supplier_stock_no_data_from_api(
    gtin_stock_service, mock_global_stock_api_client, mock_gtin_stock_repository, sample_suppliers_json_data, mocker
) -> None:
    """
    Tests synchronization when the API returns no data for a supplier.
    Verifies that no save operations are performed on the repository for that supplier.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    mock_api_response_dto_empty = GtinStockResponseDTO(
        supplier_context=SupplierContextDTO(
            retailer_id=settings.RETAILER_ID,
            retailer_gln=settings.RETAILER_GLN,
            supplier_id=87,
            supplier_gln="4042834000005",
            supplier_name="Josef Seibel",
        ),
        stock_items=[],  # Empty response
    )
    mock_global_stock_api_client.fetch_gtin_stock_data.return_value = mock_api_response_dto_empty

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    assert mock_global_stock_api_client.fetch_gtin_stock_data.called
    mock_gtin_stock_repository.save_gtin_stock_item.assert_not_called()


def test_sync_all_supplier_stock_api_error(
    gtin_stock_service, mock_global_stock_api_client, mock_gtin_stock_repository, sample_suppliers_json_data, mocker
) -> None:
    """
    Tests synchronization when the API client raises an APIError for a supplier.
    Verifies that the error is caught and synchronization continues for other suppliers.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    # Simulate API error for the first supplier, success for the second
    mock_global_stock_api_client.fetch_gtin_stock_data.side_effect = [
        APIError("API call failed for Josef Seibel"),
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=564,
                supplier_gln="5790000017089",
                supplier_name="Ecco Schuhe GmbH",
            ),
            stock_items=[
                GtinStockItemDTO(
                    gtin="5790000017001",
                    quantity=5,
                    stock_traffic_light="Yellow",
                    item_type="Pair",
                    timestamp=datetime.now(pytz.utc),
                )
            ],
        ),
    ]

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    assert mock_global_stock_api_client.fetch_gtin_stock_data.call_count == len(sample_suppliers_json_data)
    # Only the second supplier's item should be saved
    assert mock_gtin_stock_repository.save_gtin_stock_item.call_count == 1


def test_sync_all_supplier_stock_database_error(
    gtin_stock_service, mock_global_stock_api_client, mock_gtin_stock_repository, sample_suppliers_json_data, mocker
) -> None:
    """
    Tests synchronization when the repository raises a DatabaseError during save.
    Verifies that the error is caught and synchronization continues for other suppliers.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    # Mock the API client's response
    mock_api_response_items_js = [
        GtinStockItemDTO(
            gtin="1234567890001",
            quantity=10,
            stock_traffic_light="Green",
            item_type="Pair",
            timestamp=datetime.now(pytz.utc),
        )
    ]
    mock_api_response_items_ecco = [
        GtinStockItemDTO(
            gtin="5790000017001",
            quantity=5,
            stock_traffic_light="Yellow",
            item_type="Pair",
            timestamp=datetime.now(pytz.utc),
        )
    ]

    mock_global_stock_api_client.fetch_gtin_stock_data.side_effect = [
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=87,
                supplier_gln="4042834000005",
                supplier_name="Josef Seibel",
            ),
            stock_items=mock_api_response_items_js,
        ),
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=564,
                supplier_gln="5790000017089",
                supplier_name="Ecco Schuhe GmbH",
            ),
            stock_items=mock_api_response_items_ecco,
        ),
    ]

    # Configure the mock repository to raise an exception on save for the first item
    mock_gtin_stock_repository.save_gtin_stock_item.side_effect = [
        DatabaseError("DB save failed for Josef Seibel item"),
        None,  # Succeed for subsequent calls
    ]

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    # Verify that save was called for all items, despite the error on the first
    assert mock_gtin_stock_repository.save_gtin_stock_item.call_count == 2


def test_get_supplier_stock_data(gtin_stock_service, mock_gtin_stock_repository, sample_supplier_context_dto) -> None:
    """
    Tests retrieving GTIN stock data by supplier context.
    Verifies that the repository method is called and returns expected data.
    """
    mock_db_response_items = [
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
    expected_response_dto = GtinStockResponseDTO(
        supplier_context=sample_supplier_context_dto, stock_items=mock_db_response_items
    )
    mock_gtin_stock_repository.get_gtin_stock_by_supplier_context.return_value = expected_response_dto

    # Execute the service method
    result = gtin_stock_service.get_supplier_stock_data(sample_supplier_context_dto)

    # Assertions
    mock_gtin_stock_repository.get_gtin_stock_by_supplier_context.assert_called_once_with(sample_supplier_context_dto)
    assert result == expected_response_dto


# --- Tests for GlobalStockApiClient ---


def test_global_stock_api_client_get_gtins_with_stock_success(mocker) -> None:
    """Tests successful fetching of GTINs with stock."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["GTIN1", "GTIN2"]

    # Corrected: Use EAN_AVAILABILITY_API_TOKEN as per user's confirmation
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    # Capture the mocked requests.get object
    mock_requests_get = mocker.patch("requests.get", return_value=mock_response)

    client = GlobalStockApiClient()
    result = client.get_gtins_with_stock("supplier_gln_1")

    assert result == ["GTIN1", "GTIN2"]
    mock_response.raise_for_status.assert_called_once()
    # Assert on the captured mock object
    mock_requests_get.assert_called_once()
    # Corrected assertion for dictionary parameter
    assert mock_requests_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_success(mocker) -> None:
    """Tests successful fetching of GTIN availability."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}

    # Corrected: Use EAN_AVAILABILITY_API_TOKEN as per user's confirmation
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    # Capture the mocked requests.get object
    mock_requests_get = mocker.patch("requests.get", return_value=mock_response)

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert result == {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}
    mock_response.raise_for_status.assert_called_once()
    # Assert on the captured mock object
    mock_requests_get.assert_called_once()
    # Corrected assertion for dictionary parameter
    assert mock_requests_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_timeout_retry(mocker) -> None:
    """Tests retry mechanism for API timeouts."""
    # Corrected: Use EAN_AVAILABILITY_API_TOKEN as per user's confirmation
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.side_effect = [
        requests.exceptions.Timeout("Read timed out."),
        requests.exceptions.Timeout("Read timed out."),
        Mock(status_code=200, json=lambda: {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 5}]}),
    ]
    # Capture the mocked time.sleep object
    mock_time_sleep = mocker.patch("time.sleep")  # Mock time.sleep to speed up test

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_requests_get.call_count == 3
    assert result == {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 5}]}
    # Assert on the captured mock object
    mock_time_sleep.assert_called_with(5)


def test_global_stock_api_client_get_gtin_availability_request_exception(mocker) -> None:
    """Tests handling of general request exceptions."""
    # Corrected: Use EAN_AVAILABILITY_API_TOKEN as per user's confirmation
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.side_effect = requests.exceptions.RequestException("Connection error")

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_requests_get.call_count == 1
    assert result == {}  # Should return empty dict on error


def test_global_stock_api_client_fetch_gtin_stock_data(mocker, sample_supplier_context_dto) -> None:
    """Tests the orchestration of fetch_gtin_stock_data."""
    # Corrected: Use EAN_AVAILABILITY_API_TOKEN as per user's confirmation
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()

    mock_get_gtins_with_stock = mocker.patch.object(client, "get_gtins_with_stock", return_value=["GTIN1", "GTIN2"])
    mock_get_gtin_availability = mocker.patch.object(client, "get_gtin_availability")

    # Configure mock responses for get_gtin_availability
    mock_get_gtin_availability.side_effect = [
        {
            "stocksQueryResult": [
                {
                    "gtin": "GTIN1",
                    "quantity": 10,
                    "stockTrafficLight": "Green",
                    "type": 1,
                    "timestamp": "2023-01-01T10:00:00Z",
                }
            ]
        },
        {
            "stocksQueryResult": [
                {
                    "gtin": "GTIN2",
                    "quantity": 5,
                    "stockTrafficLight": "Yellow",
                    "type": 2,
                    "timestamp": "2023-01-01T11:00:00Z",
                }
            ]
        },
    ]
    mocker.patch("time.sleep")  # Mock sleep calls

    result_dto = client.fetch_gtin_stock_data(sample_supplier_context_dto)

    mock_get_gtins_with_stock.assert_called_once_with(sample_supplier_context_dto.supplier_gln)
    assert mock_get_gtin_availability.call_count == 2  # Called for GTIN1 and GTIN2

    assert isinstance(result_dto, GtinStockResponseDTO)
    assert result_dto.supplier_context == sample_supplier_context_dto
    assert len(result_dto.stock_items) == 2
    assert result_dto.stock_items[0].gtin == "GTIN1"
    assert result_dto.stock_items[0].quantity == 10
    assert result_dto.stock_items[0].stock_traffic_light == "Green"
    assert result_dto.stock_items[0].item_type == "Pair"
    assert result_dto.stock_items[0].timestamp.year == 2023
    assert result_dto.stock_items[1].gtin == "GTIN2"
    assert result_dto.stock_items[1].quantity == 5
    assert result_dto.stock_items[1].stock_traffic_light == "Yellow"
    assert result_dto.stock_items[1].item_type == "Set"
    assert result_dto.stock_items[1].timestamp.year == 2023


# --- Tests for MySQLGtinStockRepository (interaction, not actual DB) ---


def test_mysql_gtin_stock_repository_create_tables_success(mocker) -> None:
    """
    Tests that create_tables attempts to connect to DB and execute SQL queries.
    Uses a context manager to mock the connection and cursor.
    """
    # Mock the mysql.connector.connect function and its return values
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLGtinStockRepository()

    # Ensure that _connection is initially None or disconnected for a fresh mock
    repo._connection = None

    repo.create_tables()

    # Assertions
    mock_connection.assert_called_once()  # Verify connection attempt
    mock_cursor.execute.assert_called()  # Verify SQL commands were executed
    assert mock_cursor.execute.call_count == 1  # Only one table creation for GTIN stock
    mock_connection.return_value.commit.assert_called_once()  # Verify commit
    mock_cursor.close.assert_called_once()  # Verify cursor closed


def test_mysql_gtin_stock_repository_save_gtin_stock_item(mocker, sample_supplier_context_dto) -> None:
    """
    Tests that save_gtin_stock_item calls the correct SQL INSERT/UPDATE.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLGtinStockRepository()
    repo._connection = None  # Ensure a fresh mocked connection

    item_dto = GtinStockItemDTO(
        gtin="1234567890001",
        quantity=10,
        stock_traffic_light="Green",
        item_type="Pair",
        timestamp=datetime.now(pytz.utc),
    )

    repo.save_gtin_stock_item(sample_supplier_context_dto, item_dto)

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()
    # Apply .strip() to the actual SQL query string before asserting
    assert mock_cursor.execute.call_args[0][0].strip().startswith("INSERT INTO pds_gtin_stock")
    mock_connection.return_value.commit.assert_called_once()
    mock_cursor.close.assert_called_once()


def test_mysql_gtin_stock_repository_get_gtin_stock_by_supplier_context(mocker, sample_supplier_context_dto) -> None:
    """
    Tests that get_gtin_stock_by_supplier_context calls SELECT and parses results.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLGtinStockRepository()
    repo._connection = None

    # Simulate database rows returned
    mock_cursor.fetchall.return_value = [
        {
            "retailer_id": sample_supplier_context_dto.retailer_id,
            "retailer_gln": sample_supplier_context_dto.retailer_gln,
            "supplier_id": sample_supplier_context_dto.supplier_id,
            "supplier_gln": sample_supplier_context_dto.supplier_gln,
            "supplier_name": sample_supplier_context_dto.supplier_name,
            "gtin": "1234567890001",
            "quantity": 10,
            "stock_traffic_light": "Green",
            "item_type": "Pair",
            "timestamp": datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.utc),
        },
        {
            "retailer_id": sample_supplier_context_dto.retailer_id,
            "retailer_gln": sample_supplier_context_dto.retailer_gln,
            "supplier_id": sample_supplier_context_dto.supplier_id,
            "supplier_gln": sample_supplier_context_dto.supplier_gln,
            "supplier_name": sample_supplier_context_dto.supplier_name,
            "gtin": "1234567890002",
            "quantity": 0,
            "stock_traffic_light": "Red",
            "item_type": "Pair",
            "timestamp": datetime(2023, 1, 1, 11, 0, 0, tzinfo=pytz.utc),
        },
    ]

    result = repo.get_gtin_stock_by_supplier_context(sample_supplier_context_dto)

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()
    assert mock_cursor.execute.call_args[0][0].strip().startswith("SELECT gtin, quantity, stock_traffic_light")
    assert mock_cursor.execute.call_args[0][1] == (
        sample_supplier_context_dto.supplier_gln,
        sample_supplier_context_dto.retailer_gln,
    )
    mock_cursor.close.assert_called_once()

    assert isinstance(result, GtinStockResponseDTO)
    assert result.supplier_context == sample_supplier_context_dto
    assert len(result.stock_items) == 2
    assert result.stock_items[0].gtin == "1234567890001"
    assert result.stock_items[0].quantity == 10
    assert result.stock_items[0].stock_traffic_light == "Green"
    assert result.stock_items[0].item_type == "Pair"
    assert result.stock_items[0].timestamp.year == 2023

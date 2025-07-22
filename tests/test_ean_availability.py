"""Tests for the EAN Availability domain."""

from unittest.mock import Mock

import pytest

from src.common.dtos.availability_dtos import EANAvailabilityItemDTO, EANAvailabilityResponseDTO, SupplierRequestDTO
from src.common.exceptions.custom_exceptions import APIError, DatabaseError

# Import necessary classes and DTOs
from src.product_availability_domain.application.ean_availability_service import EANAvailabilityApplicationService
from src.product_availability_domain.infrastructure.api_clients.ean_availability_api_client import (
    EANAvailabilityApiClient,
)
from src.product_availability_domain.infrastructure.persistence.mysql_ean_availability_repository import (
    MySQLEANAvailabilityRepository,
)

# --- Fixtures for common test objects ---


@pytest.fixture
def mock_ean_availability_repository() -> Mock:
    """Mock for MySQLEANAvailabilityRepository."""
    return Mock(spec=MySQLEANAvailabilityRepository)


@pytest.fixture
def mock_ean_availability_api_client() -> Mock:
    """Mock for EANAvailabilityApiClient."""
    return Mock(spec=EANAvailabilityApiClient)


@pytest.fixture
def ean_availability_service(
    mock_ean_availability_repository: Mock, mock_ean_availability_api_client: Mock
) -> EANAvailabilityApplicationService:
    """Instance of EANAvailabilityApplicationService with mocked dependencies."""
    return EANAvailabilityApplicationService(
        availability_repo=mock_ean_availability_repository,
        api_client=mock_ean_availability_api_client,
    )


@pytest.fixture
def sample_supplier_request_dto() -> SupplierRequestDTO:
    """Sample SupplierRequestDTO for tests."""
    return SupplierRequestDTO(
        retailer_id="RET001",
        supplier_id="SUP007",
        supplier_gln="1234567890123",
        supplier_name="Example Supplier Corp",
    )


@pytest.fixture
def sample_eans_to_fetch() -> list[str]:
    """Sample list of EANs to fetch."""
    return ["1234567890001", "1234567890002", "1234567890003"]


# --- Tests for EANAvailabilityApplicationService ---


def test_sync_ean_availability_success(
    ean_availability_service: EANAvailabilityApplicationService,
    mock_ean_availability_api_client: Mock,
    mock_ean_availability_repository: Mock,
    sample_supplier_request_dto: SupplierRequestDTO,
    sample_eans_to_fetch: list[str],
) -> None:
    """
    Tests successful synchronization of EAN availability data.
    Verifies that the API client is called and data is saved to the repository.
    """
    # Mock the API client's response
    mock_api_response_items = [
        EANAvailabilityItemDTO(ean="1234567890001", quantity=10, price=99.99),
        EANAvailabilityItemDTO(ean="1234567890002", quantity=0, price=49.99),
        EANAvailabilityItemDTO(ean="1234567890003", quantity=5, price=75.50),
    ]
    mock_api_response_dto = EANAvailabilityResponseDTO(
        supplier_request=sample_supplier_request_dto,
        availability_items=mock_api_response_items,
    )
    mock_ean_availability_api_client.fetch_ean_availability.return_value = mock_api_response_dto

    # Execute the service method
    ean_availability_service.sync_ean_availability(sample_supplier_request_dto, sample_eans_to_fetch)

    # Assertions
    # 1. API client was called correctly
    mock_ean_availability_api_client.fetch_ean_availability.assert_called_once_with(
        sample_supplier_request_dto,
        sample_eans_to_fetch,
    )
    # 2. Repository's save method was called for each item
    assert mock_ean_availability_repository.save_ean_availability_item.call_count == len(mock_api_response_items)
    mock_ean_availability_repository.save_ean_availability_item.assert_any_call(
        sample_supplier_request_dto,
        mock_api_response_items[0],
    )
    mock_ean_availability_repository.save_ean_availability_item.assert_any_call(
        sample_supplier_request_dto,
        mock_api_response_items[1],
    )
    mock_ean_availability_repository.save_ean_availability_item.assert_any_call(
        sample_supplier_request_dto,
        mock_api_response_items[2],
    )


def test_sync_ean_availability_no_data_from_api(
    ean_availability_service: EANAvailabilityApplicationService,
    mock_ean_availability_api_client: Mock,
    mock_ean_availability_repository: Mock,
    sample_supplier_request_dto: SupplierRequestDTO,
    sample_eans_to_fetch: list[str],
) -> None:
    """
    Tests synchronization when the API returns no data.
    Verifies that no save operations are performed on the repository.
    """
    # Mock the API client's response with empty items
    mock_api_response_dto = EANAvailabilityResponseDTO(
        supplier_request=sample_supplier_request_dto,
        availability_items=[],
    )
    mock_ean_availability_api_client.fetch_ean_availability.return_value = mock_api_response_dto

    # Execute the service method
    ean_availability_service.sync_ean_availability(sample_supplier_request_dto, sample_eans_to_fetch)

    # Assertions
    mock_ean_availability_api_client.fetch_ean_availability.assert_called_once()
    mock_ean_availability_repository.save_ean_availability_item.assert_not_called()


def test_sync_ean_availability_api_error(
    ean_availability_service: EANAvailabilityApplicationService,
    mock_ean_availability_api_client: Mock,
    mock_ean_availability_repository: Mock,
    sample_supplier_request_dto: SupplierRequestDTO,
    sample_eans_to_fetch: list[str],
) -> None:
    """
    Tests synchronization when the API client raises an APIError.
    Verifies that the error is propagated and no save operations occur.
    """
    # Configure the mock API client to raise an exception
    mock_ean_availability_api_client.fetch_ean_availability.side_effect = APIError("API call failed")

    # Expect the exception to be raised
    with pytest.raises(APIError):
        ean_availability_service.sync_ean_availability(sample_supplier_request_dto, sample_eans_to_fetch)

    # Verify that no save operations were attempted
    mock_ean_availability_repository.save_ean_availability_item.assert_not_called()


def test_sync_ean_availability_database_error(
    ean_availability_service: EANAvailabilityApplicationService,
    mock_ean_availability_api_client: Mock,
    mock_ean_availability_repository: Mock,
    sample_supplier_request_dto: SupplierRequestDTO,
    sample_eans_to_fetch: list[str],
) -> None:
    """
    Tests synchronization when the repository raises a DatabaseError during save.
    Verifies that the error is propagated.
    """
    # Mock the API client's response
    mock_api_response_items = [EANAvailabilityItemDTO(ean="1234567890001", quantity=10, price=99.99)]
    mock_api_response_dto = EANAvailabilityResponseDTO(
        supplier_request=sample_supplier_request_dto,
        availability_items=mock_api_response_items,
    )
    mock_ean_availability_api_client.fetch_ean_availability.return_value = mock_api_response_dto

    # Configure the mock repository to raise an exception on save
    mock_ean_availability_repository.save_ean_availability_item.side_effect = DatabaseError("DB save failed")

    # Expect the exception to be raised
    with pytest.raises(DatabaseError):
        ean_availability_service.sync_ean_availability(sample_supplier_request_dto, sample_eans_to_fetch)

    # Verify that save was called at least once before the error
    mock_ean_availability_repository.save_ean_availability_item.assert_called_once()


def test_get_ean_availabilities_by_supplier(
    ean_availability_service: EANAvailabilityApplicationService,
    mock_ean_availability_repository: Mock,
    sample_supplier_request_dto: SupplierRequestDTO,
) -> None:
    """
    Tests retrieving EAN availabilities by supplier GLN.
    Verifies that the repository method is called and returns expected data.
    """
    mock_db_response_items = [
        EANAvailabilityItemDTO(ean="1234567890001", quantity=10, price=99.99),
        EANAvailabilityItemDTO(ean="1234567890002", quantity=0, price=49.99),
    ]
    expected_response_dto = EANAvailabilityResponseDTO(
        supplier_request=sample_supplier_request_dto,
        availability_items=mock_db_response_items,
    )
    mock_ean_availability_repository.get_ean_availabilities_by_supplier.return_value = [expected_response_dto]

    # Execute the service method
    result = ean_availability_service.get_ean_availabilities_by_supplier(sample_supplier_request_dto.supplier_gln)

    # Assertions
    mock_ean_availability_repository.get_ean_availabilities_by_supplier.assert_called_once_with(
        sample_supplier_request_dto.supplier_gln,
    )
    assert len(result) == 1
    assert result[0] == expected_response_dto


# --- Tests for MySQLEANAvailabilityRepository (focused on interaction, not actual DB) ---


def test_mysql_ean_availability_repository_create_tables_success(mocker: Mock) -> None:
    """
    Tests that create_tables attempts to connect to DB and execute SQL queries.
    Uses a context manager to mock the connection and cursor.
    """
    # Mock the mysql.connector.connect function and its return values
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLEANAvailabilityRepository()

    # Ensure that _connection is initially None or disconnected for a fresh mock
    repo._connection = None

    repo.create_tables()

    # Assertions
    mock_connection.assert_called_once()  # Verify connection attempt
    mock_cursor.execute.assert_called()  # Verify SQL commands were executed
    # We can check specific calls if needed, but for simplicity, just check it was called.
    assert mock_cursor.execute.call_count == 1  # Only one table creation for EAN in this repo
    mock_connection.return_value.commit.assert_called_once()  # Verify commit
    mock_cursor.close.assert_called_once()  # Verify cursor closed


def test_mysql_ean_availability_repository_save_ean_availability_item(
    mocker: Mock, sample_supplier_request_dto: SupplierRequestDTO
) -> None:
    """
    Tests that save_ean_availability_item calls the correct SQL INSERT/UPDATE.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLEANAvailabilityRepository()
    repo._connection = None  # Ensure a fresh mocked connection

    item_dto = EANAvailabilityItemDTO(ean="1234567890001", quantity=10, price=99.99)

    repo.save_ean_availability_item(sample_supplier_request_dto, item_dto)

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()
    # Apply .strip() to the actual SQL query string before asserting
    assert mock_cursor.execute.call_args[0][0].strip().startswith("INSERT INTO pds_ean_availabilities")
    mock_connection.return_value.commit.assert_called_once()
    mock_cursor.close.assert_called_once()


def test_mysql_ean_availability_repository_get_ean_availabilities_by_supplier(
    mocker: Mock, sample_supplier_request_dto: SupplierRequestDTO
) -> None:
    """
    Tests that get_ean_availabilities_by_supplier calls SELECT and parses results.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLEANAvailabilityRepository()
    repo._connection = None

    # Simulate database rows returned
    mock_cursor.fetchall.return_value = [
        {
            "retailer_id": sample_supplier_request_dto.retailer_id,
            "supplier_id": sample_supplier_request_dto.supplier_id,
            "supplier_gln": sample_supplier_request_dto.supplier_gln,
            "supplier_name": sample_supplier_request_dto.supplier_name,
            "ean": "1234567890001",
            "quantity": 10,
            "price": 99.99,
        },
        {
            "retailer_id": sample_supplier_request_dto.retailer_id,
            "supplier_id": sample_supplier_request_dto.supplier_id,
            "supplier_gln": sample_supplier_request_dto.supplier_gln,
            "supplier_name": sample_supplier_request_dto.supplier_name,
            "ean": "1234567890002",
            "quantity": 0,
            "price": 49.99,
        },
    ]

    result = repo.get_ean_availabilities_by_supplier(sample_supplier_request_dto.supplier_gln)

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()
    # Apply .strip() to the actual SQL query string before asserting
    assert mock_cursor.execute.call_args[0][0].strip().startswith("SELECT retailer_id, supplier_id, supplier_gln")
    mock_cursor.close.assert_called_once()

    assert len(result) == 1
    assert result[0].supplier_request == sample_supplier_request_dto
    assert len(result[0].availability_items) == 2
    assert result[0].availability_items[0].ean == "1234567890001"

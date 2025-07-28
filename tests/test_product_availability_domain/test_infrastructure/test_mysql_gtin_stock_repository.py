# tests/test_product_availability_domain/test_infrastructure/test_mysql_gtin_stock_repository.py

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
import pytz
from mysql.connector import Error

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.common.exceptions.custom_exceptions import DatabaseError
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)


def test_mysql_gtin_stock_repository_create_tables_success(mocker) -> None:
    """
    Tests that create_tables attempts to connect to DB and execute SQL queries.
    Uses a context manager to mock the connection and cursor.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLGtinStockRepository()
    repo._connection = None

    repo.create_tables()

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called()
    assert mock_cursor.execute.call_count == 1
    mock_connection.return_value.commit.assert_called_once()
    mock_cursor.close.assert_called_once()


def test_mysql_gtin_stock_repository_save_gtin_stock_item(
    mocker, sample_supplier_context_dto, sample_gtin_stock_item_dto_js
) -> None:
    """
    Tests that save_gtin_stock_item calls the correct SQL INSERT/UPDATE.
    """
    mock_connection = mocker.patch("mysql.connector.connect")
    mock_cursor = Mock()
    mock_connection.return_value.cursor.return_value = mock_cursor

    repo = MySQLGtinStockRepository()
    repo._connection = None

    repo.save_gtin_stock_item(sample_supplier_context_dto, sample_gtin_stock_item_dto_js)

    mock_connection.assert_called_once()
    mock_cursor.execute.assert_called_once()
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
            "retailer_id": "NOT_USED",  # These fields are no longer in the DB schema for this table
            "retailer_gln": "NOT_USED",
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
            "retailer_id": "NOT_USED",
            "retailer_gln": "NOT_USED",
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
    # FIX: Assert only for supplier_gln, as retailer_gln is no longer a parameter for this specific query
    assert mock_cursor.execute.call_args[0][1] == (sample_supplier_context_dto.supplier_gln,)
    mock_cursor.close.assert_called_once()

    assert isinstance(result, GtinStockResponseDTO)
    assert result.supplier_context == sample_supplier_context_dto
    assert len(result.stock_items) == 2
    assert result.stock_items[0].gtin == "1234567890001"
    assert result.stock_items[0].quantity == 10
    assert result.stock_items[0].stock_traffic_light == "Green"
    assert result.stock_items[0].item_type == "Pair"
    assert result.stock_items[0].timestamp.year == 2023


# Helper fixture to provide a fresh repository instance with mocked settings
@pytest.fixture
def mysql_gtin_stock_repository_with_mock_settings(mocker) -> MySQLGtinStockRepository:
    """Provides an instance of MySQLGtinStockRepository with mocked settings."""
    mocker.patch.object(settings, "DB_HOST", "localhost")
    mocker.patch.object(settings, "DB_DATABASE", "test_db")
    mocker.patch.object(settings, "DB_USER", "test_user")
    mocker.patch.object(settings, "DB_PASSWORD", "test_password")
    return MySQLGtinStockRepository()


@patch("mysql.connector.connect")
def test_get_all_gtin_codes_success(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test successful retrieval of GTIN codes."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True

    expected_gtins = [("1234567890123",), ("1234567890124",), ("1234567890125",)]
    mock_cursor.fetchall.return_value = expected_gtins

    # Act
    result = mysql_gtin_stock_repository_with_mock_settings.get_all_gtin_codes()

    # Assert
    expected_result = ["1234567890123", "1234567890124", "1234567890125"]
    assert result == expected_result
    mock_cursor.execute.assert_called_once_with(
        "SELECT DISTINCT gtin FROM pds_gtin_stock WHERE gtin IS NOT NULL AND gtin != ''"
    )
    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_get_all_gtin_codes_empty_result(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test retrieval when no GTIN codes exist."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True
    mock_cursor.fetchall.return_value = []

    # Act
    result = mysql_gtin_stock_repository_with_mock_settings.get_all_gtin_codes()

    # Assert
    assert result == []
    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_get_all_gtin_codes_database_error(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test handling of database errors during GTIN retrieval."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True
    mock_cursor.execute.side_effect = Error("Database connection failed")

    # Act & Assert
    with pytest.raises(DatabaseError, match="Error fetching GTIN codes"):
        mysql_gtin_stock_repository_with_mock_settings.get_all_gtin_codes()

    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_get_unique_supplier_glns_success(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test successful retrieval of supplier GLNs."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True

    expected_glns = [("5790000017089",), ("1234567890001",), ("9876543210001",)]
    mock_cursor.fetchall.return_value = expected_glns

    # Act
    result = mysql_gtin_stock_repository_with_mock_settings.get_unique_supplier_glns()

    # Assert
    expected_result = ["5790000017089", "1234567890001", "9876543210001"]
    assert result == expected_result
    mock_cursor.execute.assert_called_once_with(
        "SELECT DISTINCT supplier_gln FROM pds_gtin_stock WHERE supplier_gln IS NOT NULL AND supplier_gln != ''"
    )
    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_get_unique_supplier_glns_empty_result(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test retrieval when no supplier GLNs exist."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True
    mock_cursor.fetchall.return_value = []

    # Act
    result = mysql_gtin_stock_repository_with_mock_settings.get_unique_supplier_glns()

    # Assert
    assert result == []
    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_get_unique_supplier_glns_database_error(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test handling of database errors during supplier GLN retrieval."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True
    mock_cursor.execute.side_effect = Error("Database connection failed")

    # Act & Assert
    with pytest.raises(DatabaseError, match="Error fetching supplier GLNs"):
        mysql_gtin_stock_repository_with_mock_settings.get_unique_supplier_glns()

    mock_cursor.close.assert_called_once()


@patch("mysql.connector.connect")
def test_connection_reuse(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test that connection is reused when still connected."""
    # Arrange
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_connection.is_connected.return_value = True
    mock_cursor.fetchall.return_value = []

    # Act
    mysql_gtin_stock_repository_with_mock_settings.get_all_gtin_codes()
    mysql_gtin_stock_repository_with_mock_settings.get_unique_supplier_glns()

    # Assert
    mock_connect.assert_called_once()

    assert mock_cursor.close.call_count == 2
    assert mock_cursor.execute.call_count == 2


@patch("mysql.connector.connect")
def test_connection_error(
    mock_connect: Mock, mysql_gtin_stock_repository_with_mock_settings: MySQLGtinStockRepository
) -> None:
    """Test handling of connection errors."""
    # Arrange
    mock_connect.side_effect = Error("Connection failed")

    # Act & Assert
    with pytest.raises(DatabaseError, match="Failed to connect to MySQL"):
        mysql_gtin_stock_repository_with_mock_settings.get_all_gtin_codes()

    mock_connect.assert_called_once()

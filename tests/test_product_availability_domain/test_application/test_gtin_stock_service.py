# tests/test_gtin_stock_application_service.py
"""Tests for the GTIN Stock Application Service."""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import pytz

from src.common.config.settings import (
    settings,  # Required for SupplierContextDTO creation with settings
)

# Import DTOs and exceptions if not already covered by fixtures' imports
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.common.exceptions.custom_exceptions import APIError, DatabaseError

# All fixtures (mock_gtin_stock_repository, mock_global_stock_api_client, gtin_stock_service,
# sample_supplier_context_dto, sample_suppliers_json_data, sample_gtin_stock_item_dto_list,
# sample_gtin_stock_item_dto_list_ecco) are automatically available from conftest.py


def test_sync_all_supplier_stock_success(
    gtin_stock_service,
    mock_global_stock_api_client,
    mock_gtin_stock_repository,
    sample_suppliers_json_data,
    sample_gtin_stock_item_dto_list,
    sample_gtin_stock_item_dto_list_ecco,
    mocker,
) -> None:
    """
    Tests successful synchronization of GTIN stock data for multiple suppliers.
    Verifies API client calls and repository batch save operations.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    mock_global_stock_api_client.fetch_gtin_stock_data.side_effect = [
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=87,
                supplier_gln="4042834000005",
                supplier_name="Josef Seibel",
            ),
            stock_items=sample_gtin_stock_item_dto_list,
        ),
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=564,
                supplier_gln="5790000017089",
                supplier_name="Ecco Schuhe GmbH",
            ),
            stock_items=sample_gtin_stock_item_dto_list_ecco,
        ),
    ]

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    assert mock_global_stock_api_client.fetch_gtin_stock_data.call_count == len(sample_suppliers_json_data)

    # Assert batch_save_gtin_stock_items was called twice (once for each supplier)
    assert mock_gtin_stock_repository.batch_save_gtin_stock_items.call_count == len(sample_suppliers_json_data)

    first_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=87,
        supplier_gln="4042834000005",
        supplier_name="Josef Seibel",
    )
    mock_gtin_stock_repository.batch_save_gtin_stock_items.assert_any_call(
        first_supplier_context, sample_gtin_stock_item_dto_list
    )

    second_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=564,
        supplier_gln="5790000017089",
        supplier_name="Ecco Schuhe GmbH",
    )
    mock_gtin_stock_repository.batch_save_gtin_stock_items.assert_any_call(
        second_supplier_context, sample_gtin_stock_item_dto_list_ecco
    )

    # Ensure individual save_gtin_stock_item was NOT called by sync_all_supplier_stock
    mock_gtin_stock_repository.save_gtin_stock_item.assert_not_called()


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
    gtin_stock_service,
    mock_global_stock_api_client,
    mock_gtin_stock_repository,
    sample_suppliers_json_data,
    sample_gtin_stock_item_dto_list_ecco,
    mocker,
) -> None:
    """
    Tests synchronization when the API client raises an APIError for a supplier.
    Verifies that the error is caught and synchronization continues for other suppliers.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

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
            stock_items=sample_gtin_stock_item_dto_list_ecco,
        ),
    ]

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    assert mock_global_stock_api_client.fetch_gtin_stock_data.call_count == len(sample_suppliers_json_data)

    # Assert batch_save_gtin_stock_items was called once for the successful supplier
    assert mock_gtin_stock_repository.batch_save_gtin_stock_items.call_count == 1

    # Verify that the correct supplier's data was attempted to be saved
    second_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=564,
        supplier_gln="5790000017089",
        supplier_name="Ecco Schuhe GmbH",
    )
    mock_gtin_stock_repository.batch_save_gtin_stock_items.assert_called_once_with(
        second_supplier_context, sample_gtin_stock_item_dto_list_ecco
    )

    # Ensure individual save_gtin_stock_item was NOT called
    mock_gtin_stock_repository.save_gtin_stock_item.assert_not_called()


def test_sync_all_supplier_stock_database_error(
    gtin_stock_service,
    mock_global_stock_api_client,
    mock_gtin_stock_repository,
    sample_suppliers_json_data,
    sample_gtin_stock_item_dto_list,  # For JS
    sample_gtin_stock_item_dto_list_ecco,  # For Ecco
    mocker,
) -> None:
    """
    Tests synchronization when the repository raises a DatabaseError during batch save.
    Verifies that the error is caught and synchronization continues for other suppliers.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(sample_suppliers_json_data)))
    mocker.patch("json.load", return_value=sample_suppliers_json_data)

    mock_global_stock_api_client.fetch_gtin_stock_data.side_effect = [
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=87,
                supplier_gln="4042834000005",
                supplier_name="Josef Seibel",
            ),
            stock_items=[sample_gtin_stock_item_dto_list[0]],  # Only one item from JS for this specific test case
        ),
        GtinStockResponseDTO(
            supplier_context=SupplierContextDTO(
                retailer_id=settings.RETAILER_ID,
                retailer_gln=settings.RETAILER_GLN,
                supplier_id=564,
                supplier_gln="5790000017089",
                supplier_name="Ecco Schuhe GmbH",
            ),
            stock_items=sample_gtin_stock_item_dto_list_ecco,
        ),
    ]

    # Configure the mock repository to raise an exception on the first batch save (Josef Seibel)
    # and succeed on the second (Ecco).
    mock_gtin_stock_repository.batch_save_gtin_stock_items.side_effect = [
        DatabaseError("DB batch save failed for Josef Seibel items"),
        None,  # Succeed for Ecco's batch
    ]

    gtin_stock_service.sync_all_supplier_stock("dummy_path/suppliers.json")

    # Verify that batch_save_gtin_stock_items was called for both suppliers,
    # despite the error on the first one.
    assert mock_gtin_stock_repository.batch_save_gtin_stock_items.call_count == len(sample_suppliers_json_data)

    first_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=87,
        supplier_gln="4042834000005",
        supplier_name="Josef Seibel",
    )
    # Assert that batch_save was called for Josef Seibel with its item
    mock_gtin_stock_repository.batch_save_gtin_stock_items.assert_any_call(
        first_supplier_context, [sample_gtin_stock_item_dto_list[0]]
    )

    second_supplier_context = SupplierContextDTO(
        retailer_id=settings.RETAILER_ID,
        retailer_gln=settings.RETAILER_GLN,
        supplier_id=564,
        supplier_gln="5790000017089",
        supplier_name="Ecco Schuhe GmbH",
    )
    # Assert that batch_save was called for Ecco with its items
    mock_gtin_stock_repository.batch_save_gtin_stock_items.assert_any_call(
        second_supplier_context, sample_gtin_stock_item_dto_list_ecco
    )

    # Ensure individual save_gtin_stock_item was NOT called
    mock_gtin_stock_repository.save_gtin_stock_item.assert_not_called()


def test_get_supplier_stock_data(gtin_stock_service, mock_gtin_stock_repository, sample_supplier_context_dto) -> None:
    """
    Tests retrieving GTIN stock data by supplier context.
    Verifies that the repository method is called and returns expected data.
    """
    # Create the expected DTOs based on what your service should receive from the repository mock
    mock_db_response_items = [
        GtinStockItemDTO(
            gtin="1234567890001",
            quantity=10,
            stock_traffic_light="Green",
            item_type="Pair",
            timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.utc),
        ),
        GtinStockItemDTO(
            gtin="1234567890002",
            quantity=0,
            stock_traffic_light="Red",
            item_type="Pair",
            timestamp=datetime(2023, 1, 1, 11, 0, 0, tzinfo=pytz.utc),
        ),
    ]
    expected_response_dto = GtinStockResponseDTO(
        supplier_context=sample_supplier_context_dto, stock_items=mock_db_response_items
    )
    mock_gtin_stock_repository.get_gtin_stock_by_supplier_context.return_value = expected_response_dto

    result = gtin_stock_service.get_supplier_stock_data(sample_supplier_context_dto)

    mock_gtin_stock_repository.get_gtin_stock_by_supplier_context.assert_called_once_with(sample_supplier_context_dto)
    assert result == expected_response_dto


def test_get_all_gtin_codes_success(gtin_stock_service, mock_gtin_stock_repository) -> None:
    """Test successful retrieval of GTIN codes."""
    expected_gtins = ["1234567890123", "1234567890124", "1234567890125"]
    mock_gtin_stock_repository.get_all_gtin_codes.return_value = expected_gtins

    result = gtin_stock_service.get_all_gtin_codes()

    assert result == expected_gtins
    mock_gtin_stock_repository.get_all_gtin_codes.assert_called_once()


def test_get_all_gtin_codes_empty_list(gtin_stock_service, mock_gtin_stock_repository) -> None:
    """Test retrieval when no GTIN codes exist."""
    mock_gtin_stock_repository.get_all_gtin_codes.return_value = []

    result = gtin_stock_service.get_all_gtin_codes()

    assert result == []
    mock_gtin_stock_repository.get_all_gtin_codes.assert_called_once()


def test_get_unique_supplier_glns_success(gtin_stock_service, mock_gtin_stock_repository) -> None:
    """Test successful retrieval of supplier GLNs."""
    expected_glns = ["5790000017089", "1234567890001", "9876543210001"]
    mock_gtin_stock_repository.get_unique_supplier_glns.return_value = expected_glns

    result = gtin_stock_service.get_unique_supplier_glns()

    assert result == expected_glns
    mock_gtin_stock_repository.get_unique_supplier_glns.assert_called_once()


def test_get_unique_supplier_glns_empty_list(gtin_stock_service, mock_gtin_stock_repository) -> None:
    """Test retrieval when no supplier GLNs exist."""
    mock_gtin_stock_repository.get_unique_supplier_glns.return_value = []

    result = gtin_stock_service.get_unique_supplier_glns()

    assert result == []
    mock_gtin_stock_repository.get_unique_supplier_glns.assert_called_once()


def test_service_delegates_to_repository(gtin_stock_service, mock_gtin_stock_repository) -> None:
    """Test that service properly delegates calls to repository."""
    test_gtins = ["test_gtin_1", "test_gtin_2"]
    test_glns = ["test_gln_1", "test_gln_2"]
    mock_gtin_stock_repository.get_all_gtin_codes.return_value = test_gtins
    mock_gtin_stock_repository.get_unique_supplier_glns.return_value = test_glns

    gtin_result = gtin_stock_service.get_all_gtin_codes()
    gln_result = gtin_stock_service.get_unique_supplier_glns()

    assert gtin_result == test_gtins
    assert gln_result == test_glns
    mock_gtin_stock_repository.get_all_gtin_codes.assert_called_once()
    mock_gtin_stock_repository.get_unique_supplier_glns.assert_called_once()

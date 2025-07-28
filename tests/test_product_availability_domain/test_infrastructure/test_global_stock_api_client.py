# tests/test_product_availability_domain/test_infrastructure/test_global_stock_api_client.py
"""Tests for the GlobalStockApiClient."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import pytz
import requests

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import (
    GlobalStockApiClient,
)

# All fixtures (mock_settings_retailer_info, sample_supplier_context_dto) are automatically available from conftest.py


def test_global_stock_api_client_get_gtins_with_stock_success(mocker) -> None:
    """Tests successful fetching of GTINs with stock."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["GTIN1", "GTIN2"]

    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()
    # Mock the session's get method
    mock_session_get = mocker.patch.object(client.session, "get", return_value=mock_response)

    result = client.get_gtins_with_stock("supplier_gln_1")

    assert result == ["GTIN1", "GTIN2"]
    mock_response.raise_for_status.assert_called_once()
    mock_session_get.assert_called_once()  # Assert on session.get
    assert mock_session_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_success(mocker) -> None:
    """Tests successful fetching of GTIN availability."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}

    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()
    # Mock the session's get method
    mock_session_get = mocker.patch.object(client.session, "get", return_value=mock_response)

    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert result == {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}
    mock_response.raise_for_status.assert_called_once()
    mock_session_get.assert_called_once()  # Assert on session.get
    assert mock_session_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_timeout_retry(mocker) -> None:
    """
    Tests fetching of GTIN availability when the API call times out.
    Verifies that the method returns an empty dict and logs a message.
    """
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()
    mock_session_get = mocker.patch.object(client.session, "get")
    mock_session_get.side_effect = requests.exceptions.Timeout("Read timed out.")  # Only one timeout needed

    mock_time_sleep = mocker.patch("time.sleep")  # Still mock, but won't be called by get_gtin_availability on Timeout

    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_session_get.call_count == 1  # The method exits after the first timeout
    assert result == {}  # Returns an empty dict on timeout
    mock_time_sleep.assert_not_called()  # time.sleep is not called by get_gtin_availability on Timeout


def test_global_stock_api_client_get_gtin_availability_request_exception(mocker) -> None:
    """Tests handling of general request exceptions."""
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()
    mock_session_get = mocker.patch.object(client.session, "get")  # Correctly mock session.get
    mock_session_get.side_effect = requests.exceptions.RequestException("Connection error")

    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_session_get.call_count == 1  # Method exits after the first exception
    assert result == {}  # Returns an empty dict on RequestException


def test_global_stock_api_client_fetch_gtin_stock_data(mocker, sample_supplier_context_dto) -> None:
    """
    Tests the orchestration of fetch_gtin_stock_data (which now delegates to fetch_gtin_stock_data_optimized).
    We mock the underlying methods called by fetch_gtin_stock_data_optimized.
    """
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()

    mock_get_gtins_with_stock = mocker.patch.object(client, "get_gtins_with_stock", return_value=["GTIN1", "GTIN2"])

    # Mock _process_gtin_batch as this is where the actual GTIN fetching and DTO creation happens
    mock_process_gtin_batch = mocker.patch.object(client, "_process_gtin_batch")

    # Define the return value for _process_gtin_batch
    # It should return a list of GtinStockItemDTOs directly
    expected_stock_items = [
        GtinStockItemDTO(
            gtin="GTIN1",
            quantity=10,
            stock_traffic_light="Green",
            item_type="Pair",
            timestamp=datetime(2023, 1, 1, 10, 0, 0, tzinfo=pytz.utc),
        ),
        GtinStockItemDTO(
            gtin="GTIN2",
            quantity=5,
            stock_traffic_light="Yellow",
            item_type="Set",
            timestamp=datetime(2023, 1, 1, 11, 0, 0, tzinfo=pytz.utc),
        ),
    ]
    mock_process_gtin_batch.return_value = expected_stock_items

    # Mock time.sleep to prevent actual delays during test
    mocker.patch("time.sleep")

    result_dto = client.fetch_gtin_stock_data(sample_supplier_context_dto)

    mock_get_gtins_with_stock.assert_called_once_with(sample_supplier_context_dto.supplier_gln)

    # Verify that _process_gtin_batch was called with the correct arguments.
    # It should be called once with the entire list of GTINs from get_gtins_with_stock
    # (since default batch_size is 100, and we only have 2 GTINs).
    mock_process_gtin_batch.assert_called_once_with(
        ["GTIN1", "GTIN2"],
        sample_supplier_context_dto.supplier_gln,
        1,
        1,  # batch_num and total_batches for a single batch
    )

    assert isinstance(result_dto, GtinStockResponseDTO)
    assert result_dto.supplier_context == sample_supplier_context_dto
    assert len(result_dto.stock_items) == 2

    # Directly compare the stock_items, as they should be exactly what _process_gtin_batch returned
    assert result_dto.stock_items == expected_stock_items

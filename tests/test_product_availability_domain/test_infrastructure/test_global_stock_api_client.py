"""Tests for the GlobalStockApiClient."""

import pytest
from unittest.mock import Mock, patch
import requests
from datetime import datetime  # Added for GtinStockItemDTO timestamp creation
import pytz  # Added for GtinStockItemDTO timestamp creation
from src.common.config.settings import settings
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient


# All fixtures (mock_settings_retailer_info, sample_supplier_context_dto) are automatically available from conftest.py


def test_global_stock_api_client_get_gtins_with_stock_success(mocker) -> None:
    """Tests successful fetching of GTINs with stock."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["GTIN1", "GTIN2"]

    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get", return_value=mock_response)

    client = GlobalStockApiClient()
    result = client.get_gtins_with_stock("supplier_gln_1")

    assert result == ["GTIN1", "GTIN2"]
    mock_response.raise_for_status.assert_called_once()
    mock_requests_get.assert_called_once()
    assert mock_requests_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_success(mocker) -> None:
    """Tests successful fetching of GTIN availability."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}

    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get", return_value=mock_response)

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert result == {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 10}]}
    mock_response.raise_for_status.assert_called_once()
    mock_requests_get.assert_called_once()
    assert mock_requests_get.call_args[1]["params"].get("token") == "test_token"


def test_global_stock_api_client_get_gtin_availability_timeout_retry(mocker) -> None:
    """Tests retry mechanism for API timeouts."""
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.side_effect = [
        requests.exceptions.Timeout("Read timed out."),
        requests.exceptions.Timeout("Read timed out."),
        Mock(status_code=200, json=lambda: {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 5}]}),
    ]
    mock_time_sleep = mocker.patch("time.sleep")

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_requests_get.call_count == 3
    assert result == {"stocksQueryResult": [{"gtin": "GTIN1", "quantity": 5}]}
    mock_time_sleep.assert_called_with(5)


def test_global_stock_api_client_get_gtin_availability_request_exception(mocker) -> None:
    """Tests handling of general request exceptions."""
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    mock_requests_get = mocker.patch("requests.get")
    mock_requests_get.side_effect = requests.exceptions.RequestException("Connection error")

    client = GlobalStockApiClient()
    result = client.get_gtin_availability("GTIN1", "supplier_gln_1")

    assert mock_requests_get.call_count == 1
    assert result == {}


def test_global_stock_api_client_fetch_gtin_stock_data(mocker, sample_supplier_context_dto) -> None:
    """Tests the orchestration of fetch_gtin_stock_data."""
    mocker.patch.object(settings, "EAN_AVAILABILITY_API_TOKEN", "test_token")

    client = GlobalStockApiClient()

    mock_get_gtins_with_stock = mocker.patch.object(client, "get_gtins_with_stock", return_value=["GTIN1", "GTIN2"])
    mock_get_gtin_availability = mocker.patch.object(client, "get_gtin_availability")

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
    mocker.patch("time.sleep")

    result_dto = client.fetch_gtin_stock_data(sample_supplier_context_dto)

    mock_get_gtins_with_stock.assert_called_once_with(sample_supplier_context_dto.supplier_gln)
    assert mock_get_gtin_availability.call_count == 2

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

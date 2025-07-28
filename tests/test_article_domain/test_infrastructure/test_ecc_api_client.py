"""Tests for ECC API Client."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from src.article_domain.infrastructure.api_clients.ecc_api_client import ECCApiClient
from src.common.dtos.article_dtos import ArticleDataDTO
from src.common.exceptions.custom_exceptions import APIError


class TestECCApiClient:
    def setup_method(self) -> None:
        """Setup test dependencies."""
        with patch("src.article_domain.infrastructure.api_clients.ecc_api_client.settings") as mock_settings:
            mock_settings.ECC_API_BASE_URL = "https://api.example.com"
            mock_settings.ECC_API_TOKEN = "test_token"
            self.client = ECCApiClient()

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    def test_fetch_articles_by_gtin_success(self, mock_get: Mock) -> None:
        """Test successful article fetching by GTIN."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "0194891750349")]
        su_gln = "5790000017089"  # For assert'а URL
        ean = "0194891750349"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "articles": [
                {
                    "eccId": 6651663,
                    "suGln": "5790000017089",
                    "mfGln": "5790000017089",
                    "brand": "Ecco",
                    "model": "ECCO BIOM C-TRAIL W",
                    "articleName": "Outdoor",
                    "currency": "EUR",
                    "seasonTxt": "FS 2025",
                    "assortment": {"de": [{"ean": "0194891750349", "primeCost": 80.85, "retailPrice": 190}]},
                    "images": [{"media": [{"file": "https://example.com/image.jpg"}]}],
                }
            ]
        }
        mock_get.return_value = mock_response

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], ArticleDataDTO)
        assert result[0].eccId == 6651663
        assert result[0].ean == "0194891750349"

        expected_url = f"https://api.example.com/articleData/byEanAndSuGln/{ean}/{su_gln}/de"
        mock_get.assert_called_once_with(expected_url, params={"token": "test_token"}, timeout=30)

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    @patch("builtins.print")  # Added patch for print to prevent console output during test
    def test_fetch_articles_by_gtin_multiple_gtins(self, mock_print: Mock, mock_get: Mock) -> None:
        """Test fetching articles for multiple GTINs."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "0194891750349"), ("5790000017089", "0194891750356")]

        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "articles": [
                {
                    "eccId": 6651663,
                    "suGln": "5790000017089",
                    "brand": "Ecco",
                    "assortment": {"de": [{"ean": "0194891750349"}]},
                }
            ]
        }

        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "articles": [
                {
                    "eccId": 6651664,
                    "suGln": "5790000017089",
                    "brand": "Ecco",
                    "assortment": {"de": [{"ean": "0194891750356"}]},
                }
            ]
        }
        mock_get.side_effect = [mock_response_1, mock_response_2]

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 2
        assert mock_get.call_count == 2

        expected_url_1 = "https://api.example.com/articleData/byEanAndSuGln/0194891750349/5790000017089/de"
        expected_url_2 = "https://api.example.com/articleData/byEanAndSuGln/0194891750356/5790000017089/de"
        mock_get.assert_any_call(expected_url_1, params={"token": "test_token"}, timeout=30)
        mock_get.assert_any_call(expected_url_2, params={"token": "test_token"}, timeout=30)
        # Verify print calls for each API request
        mock_print.assert_any_call("Get data for 0194891750349 5790000017089")
        mock_print.assert_any_call("Get data for 0194891750356 5790000017089")

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    @patch("builtins.print")  # Added patch for print
    def test_fetch_articles_by_gtin_no_articles(self, mock_print: Mock, mock_get: Mock) -> None:
        """Test fetching when API returns no articles."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "0194891750349")]
        ean = "0194891750349"
        su_gln = "5790000017089"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"articles": []}
        mock_get.return_value = mock_response

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 0
        expected_url = f"https://api.example.com/articleData/byEanAndSuGln/{ean}/{su_gln}/de"
        mock_get.assert_called_once_with(expected_url, params={"token": "test_token"}, timeout=30)
        mock_print.assert_any_call(f"Get data for {ean} {su_gln}")
        mock_print.assert_any_call(f"No articles found for EAN: {ean}, Supplier GLN: {su_gln}")
        assert mock_print.call_count == 2  # Expect two print calls

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    @patch("builtins.print")
    def test_fetch_articles_by_gtin_request_exception(self, mock_print: Mock, mock_get: Mock) -> None:
        """Test handling of request exceptions."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "0194891750349")]
        test_gtin = "0194891750349"
        test_su_gln = "5790000017089"

        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 0
        mock_print.assert_any_call(f"Get data for {test_gtin} {test_su_gln}")  # Initial print
        mock_print.assert_any_call(
            f"API request failed for EAN {test_gtin}, Supplier GLN {test_su_gln}: Connection error"
        )  # Error print
        assert mock_print.call_count == 2  # Expect two print calls
        expected_url = f"https://api.example.com/articleData/byEanAndSuGln/{test_gtin}/{test_su_gln}/de"
        mock_get.assert_called_once_with(expected_url, params={"token": "test_token"}, timeout=30)

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    @patch("builtins.print")
    def test_fetch_articles_by_gtin_json_decode_error(self, mock_print: Mock, mock_get: Mock) -> None:
        """Test handling of JSON decode errors."""
        # Arrange
        test_gtin = "0194891750349"
        test_su_gln = "5790000017089"
        supplier_gtin_pairs = [(test_su_gln, test_gtin)]

        mock_exception_message = "Invalid JSON"
        mock_exception_doc = "some invalid json"
        mock_exception_pos = 0
        mock_json_decode_error = json.JSONDecodeError(
            mock_exception_message, doc=mock_exception_doc, pos=mock_exception_pos
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = mock_json_decode_error
        mock_get.return_value = mock_response

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 0
        # Now assert for both expected print calls
        mock_print.assert_any_call(f"Get data for {test_gtin} {test_su_gln}")

        # The str() of JSONDecodeError includes doc and pos automatically
        expected_error_message = (
            f"Failed to decode JSON response for EAN {test_gtin}, Supplier GLN {test_su_gln}: {mock_json_decode_error}"
        )
        mock_print.assert_any_call(expected_error_message)

        assert mock_print.call_count == 2  # Expected two print calls
        expected_url = f"https://api.example.com/articleData/byEanAndSuGln/{test_gtin}/{test_su_gln}/de"
        mock_get.assert_called_once_with(expected_url, params={"token": "test_token"}, timeout=30)

    def test_fetch_articles_by_gtin_no_token(self) -> None:
        """Test error when API token is not set."""
        # Arrange
        with patch("src.article_domain.infrastructure.api_clients.ecc_api_client.settings") as mock_settings:
            mock_settings.ECC_API_BASE_URL = "https://api.example.com"
            mock_settings.ECC_API_TOKEN = None
            client = ECCApiClient()

        # Act & Assert
        with pytest.raises(APIError, match="ECC_API_TOKEN is not set"):
            client.fetch_articles_by_gtin([("5790000017089", "0194891750349")])

    @patch("src.article_domain.infrastructure.api_clients.ecc_api_client.requests.get")
    def test_fetch_articles_by_gtin_empty_list(self, mock_get: Mock) -> None:
        """Test fetching with empty GTIN list."""
        # Arrange
        supplier_gtin_pairs = []

        # Act
        result = self.client.fetch_articles_by_gtin(supplier_gtin_pairs)

        # Assert
        assert len(result) == 0
        mock_get.assert_not_called()

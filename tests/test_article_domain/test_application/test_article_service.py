"""Tests for Article Application Service."""

from unittest.mock import Mock, patch

import pytest

from src.article_domain.application.article_service import ArticleApplicationService
from src.article_domain.domain.repositories.article_repository import IArticleRepository
from src.article_domain.infrastructure.api_clients.ecc_api_client import ECCApiClient
from src.common.dtos.article_dtos import ArticleDataDTO


class TestArticleApplicationService:
    def setup_method(self) -> None:
        """Setup test dependencies."""
        self.mock_repo = Mock(spec=IArticleRepository)
        self.mock_api_client = Mock(spec=ECCApiClient)
        self.service = ArticleApplicationService(self.mock_repo, self.mock_api_client)

    def test_sync_articles_from_ecc_success(self) -> None:
        """Test successful article synchronization from ECC API."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "1234567890123"), ("5790000017089", "1234567890124")]
        mock_articles = [ArticleDataDTO(eccId=1, ean="1234567890123"), ArticleDataDTO(eccId=2, ean="1234567890124")]
        self.mock_api_client.fetch_articles_by_gtin.return_value = mock_articles

        # Act
        self.service.sync_articles_from_ecc(supplier_gtin_pairs)

        # Assert
        # The API client method now also expects supplier_gtin_pairs
        self.mock_api_client.fetch_articles_by_gtin.assert_called_once_with(supplier_gtin_pairs)
        assert self.mock_repo.save_article.call_count == 2
        self.mock_repo.save_article.assert_any_call(mock_articles[0])
        self.mock_repo.save_article.assert_any_call(mock_articles[1])

    def test_sync_articles_from_ecc_no_data(self) -> None:
        """Test synchronization when API returns no data."""
        # Arrange
        supplier_gtin_pairs = [("5790000017089", "1234567890123")]
        self.mock_api_client.fetch_articles_by_gtin.return_value = []

        # Act
        self.service.sync_articles_from_ecc(supplier_gtin_pairs)

        # Assert
        self.mock_api_client.fetch_articles_by_gtin.assert_called_once_with(supplier_gtin_pairs)
        self.mock_repo.save_article.assert_not_called()

    def test_sync_articles_from_ecc_empty_gtin_list(self) -> None:
        """Test synchronization with empty GTIN list."""
        # Arrange
        supplier_gtin_pairs = []
        self.mock_api_client.fetch_articles_by_gtin.return_value = []

        # Act
        self.service.sync_articles_from_ecc(supplier_gtin_pairs)

        # Assert
        self.mock_api_client.fetch_articles_by_gtin.assert_called_once_with(supplier_gtin_pairs)
        self.mock_repo.save_article.assert_not_called()

    @patch("builtins.print")
    def test_sync_articles_prints_correct_messages(self, mock_print: Mock) -> None:
        """Test that correct messages are printed during synchronization."""
        # Arrange
        # Changed: Create supplier_gtin_pairs
        supplier_gtin_pairs = [("5790000017089", "1234567890123")]
        mock_articles = [ArticleDataDTO(eccId=1, ean="1234567890123")]
        self.mock_api_client.fetch_articles_by_gtin.return_value = mock_articles

        # Act
        self.service.sync_articles_from_ecc(supplier_gtin_pairs)

        # Assert
        # Update expected messages based on the new print statements in ArticleApplicationService
        expected_calls = [
            f"Synchronizing articles from ECC for {len(supplier_gtin_pairs)} supplier GLN and GTIN pairs",
            f"Synchronization completed. Processed {len(mock_articles)} articles.",
        ]
        for expected_call in expected_calls:
            mock_print.assert_any_call(expected_call)

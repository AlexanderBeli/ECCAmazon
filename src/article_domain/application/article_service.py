# article_domain/application/article_service.py
"""Application services for Article domain."""

import logging

from src.article_domain.domain.repositories.article_repository import IArticleRepository
from src.article_domain.infrastructure.api_clients.ecc_api_client import ECCApiClient
from src.common.dtos.article_dtos import ArticleDataDTO

logger = logging.getLogger(__name__)


class ArticleApplicationService:
    def __init__(self, article_repo: IArticleRepository, ecc_api_client: ECCApiClient) -> None:
        self.article_repo = article_repo
        self.ecc_api_client = ecc_api_client

    def sync_articles_from_ecc(self, supplier_gtin_pairs: list[tuple[str, str]]) -> None:
        """Fetches article data from ECC API using supplier GLN and GTIN pairs."""
        logger.info(f"Synchronizing articles from ECC for {len(supplier_gtin_pairs)} supplier GLN and GTIN pairs")
        article_dtos = self.ecc_api_client.fetch_articles_by_gtin(supplier_gtin_pairs)

        if not article_dtos:
            logger.warning("No data received from API for synchronization.")
            return

        for article_dto in article_dtos:
            logger.info("Saving started...")
            self.article_repo.save_article(article_dto)
        logger.info(f"Synchronization completed. Processed {len(article_dtos)} articles.")

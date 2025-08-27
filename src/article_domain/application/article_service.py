# article_domain/application/article_service.py
"""Application services for Article domain."""

import logging
from typing import Iterator

from src.article_domain.domain.repositories.article_repository import IArticleRepository
from src.article_domain.infrastructure.api_clients.ecc_api_client import ECCApiClient
from src.common.dtos.article_dtos import ArticleDataDTO

logger = logging.getLogger(__name__)


class ArticleApplicationService:

    def __init__(self, article_repo: IArticleRepository, ecc_api_client: ECCApiClient, batch_size: int = 100) -> None:
        self.article_repo = article_repo
        self.ecc_api_client = ecc_api_client
        self.batch_size = batch_size

    def _chunk_pairs(self, pairs: list[tuple[str, str]], chunk_size: int) -> Iterator[list[tuple[str, str]]]:
        """Split pairs into chunks of specified size."""
        for i in range(0, len(pairs), chunk_size):
            yield pairs[i : i + chunk_size]

    # def sync_articles_from_ecc(self, supplier_gtin_pairs: list[tuple[str, str]]) -> None:
    #     """Fetches article data from ECC API using supplier GLN and GTIN pairs."""
    #     logger.info(f"Synchronizing articles from ECC for {len(supplier_gtin_pairs)} supplier GLN and GTIN pairs")
    #     article_dtos = self.ecc_api_client.fetch_articles_by_gtin(supplier_gtin_pairs)

    #     if not article_dtos:
    #         logger.warning("No data received from API for synchronization.")
    #         return

    #     for article_dto in article_dtos:
    #         logger.info("Saving started...")
    #         self.article_repo.save_article(article_dto)
    #     logger.info(f"Synchronization completed. Processed {len(article_dtos)} articles.")

    def sync_articles_from_ecc(self, supplier_gtin_pairs: list[tuple[str, str]]) -> None:
        """Fetches and saves article data in batches from ECC API using supplier GLN and GTIN pairs."""
        total_pairs = len(supplier_gtin_pairs)
        logger.info(
            f"Starting batch synchronization for {total_pairs} supplier GLN and GTIN pairs with batch size {self.batch_size}"
        )

        processed_count = 0
        total_articles_saved = 0
        failed_batches = 0

        # Process pairs in batches
        for batch_num, batch_pairs in enumerate(self._chunk_pairs(supplier_gtin_pairs, self.batch_size), 1):
            batch_size_actual = len(batch_pairs)
            logger.info(
                f"Processing batch {batch_num}: pairs {processed_count + 1}-{processed_count + batch_size_actual} of {total_pairs}"
            )

            try:
                # Fetch articles for current batch
                article_dtos = self.ecc_api_client.fetch_articles_by_gtin(batch_pairs)

                if not article_dtos:
                    logger.warning(f"No data received from API for batch {batch_num}")
                    processed_count += batch_size_actual
                    continue

                # Save articles from current batch
                batch_saved_count = 0
                batch_failed_count = 0

                for article_dto in article_dtos:
                    try:
                        self.article_repo.save_article(article_dto)
                        batch_saved_count += 1
                    except Exception as e:
                        batch_failed_count += 1
                        gtin = getattr(article_dto, "gtin", "unknown")
                        logger.error(f"Failed to save article {gtin}: {e}")
                        continue

                total_articles_saved += batch_saved_count
                processed_count += batch_size_actual

                logger.info(
                    f"Batch {batch_num} completed: {batch_saved_count} articles saved from {len(article_dtos)} received"
                )

            except Exception as e:
                failed_batches += 1
                logger.error(f"Error processing batch {batch_num}: {e}")
                processed_count += batch_size_actual
                continue

        logger.info(f"Batch synchronization completed:")
        logger.info(f"  - Total processed pairs: {processed_count}")
        logger.info(f"  - Total saved articles: {total_articles_saved}")
        logger.info(f"  - Failed batches: {failed_batches}")

    def sync_articles_from_ecc_with_custom_batch_size(
        self, supplier_gtin_pairs: list[tuple[str, str]], batch_size: int
    ) -> None:
        """Fetches and saves article data with custom batch size."""
        original_batch_size = self.batch_size
        self.batch_size = batch_size
        try:
            self.sync_articles_from_ecc(supplier_gtin_pairs)
        finally:
            self.batch_size = original_batch_size

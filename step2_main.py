"""Main application entry point for GTIN article synchronization."""

from src.common.config.settings import settings
from src.common.exceptions.custom_exceptions import APIError, DatabaseError

# Article Domain Imports
from src.article_domain.application.article_service import ArticleApplicationService
from src.article_domain.infrastructure.persistence.mysql_article_repository import MySQLArticleRepository
from src.article_domain.infrastructure.api_clients.ecc_api_client import ECCApiClient

# GTIN Stock Domain Imports
from src.product_availability_domain.application.gtin_stock_service import GtinStockApplicationService
from src.product_availability_domain.infrastructure.persistence.mysql_gtin_stock_repository import (
    MySQLGtinStockRepository,
)
from src.product_availability_domain.infrastructure.api_clients.global_stock_api_client import GlobalStockApiClient


def setup_dependencies() -> tuple[ArticleApplicationService, GtinStockApplicationService]:
    """Initializes and wires up application dependencies."""
    # Article Domain Dependencies
    ecc_api_client = ECCApiClient()
    article_repository = MySQLArticleRepository()
    article_app_service = ArticleApplicationService(article_repo=article_repository, ecc_api_client=ecc_api_client)
    global_stock_api_client = GlobalStockApiClient()

    # GTIN Stock Domain Dependencies
    gtin_stock_repository = MySQLGtinStockRepository()
    gtin_stock_service = GtinStockApplicationService(
        stock_repo=gtin_stock_repository, api_client=global_stock_api_client
    )

    return article_app_service, gtin_stock_service


def create_article_tables() -> None:
    """Creates tables for article domain."""
    article_repo = MySQLArticleRepository()
    try:
        article_repo.create_tables()
    except DatabaseError as e:
        print(f"Error creating article database tables: {e}")
        raise
    finally:
        del article_repo


def run_gtin_article_sync() -> None:
    """Main process: get supplier GLN and GTIN pairs, fetch article data, save to MySQL."""
    create_article_tables()
    article_app_service, gtin_stock_service = setup_dependencies()

    try:
        print("\n--- Fetching supplier GLN and GTIN pairs from stock table ---")
        # Get pairs directly from repository since service might not have this method
        gtin_stock_repository = MySQLGtinStockRepository()
        supplier_gtin_pairs = gtin_stock_repository.get_all_supplier_gtin_pairs()

        if not supplier_gtin_pairs:
            print("No supplier GLN and GTIN pairs found in pds_gtin_stock table. Exiting.")
            return

        print(f"Found {len(supplier_gtin_pairs)} unique supplier GLN and GTIN pairs")

        print("\n--- Synchronizing article data using supplier GLN and GTIN pairs ---")

        article_app_service.sync_articles_from_ecc(supplier_gtin_pairs)

        print("Completed processing all supplier GLN and GTIN pairs")

    except (APIError, DatabaseError) as e:
        print(f"An error occurred during GTIN article synchronization: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise


if __name__ == "__main__":
    print("Starting GTIN article data synchronization...")
    run_gtin_article_sync()
    print("GTIN article synchronization completed.")

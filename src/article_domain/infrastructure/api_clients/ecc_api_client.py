# article_domain/infrastructure/api_clients/ecc_api_client.py
"""Client for ECC Content Article API."""

import json

import requests

from src.common.config.settings import settings
from src.common.dtos.article_dtos import ArticleDataDTO
from src.common.exceptions.custom_exceptions import APIError


class ECCApiClient:
    def __init__(self) -> None:
        self.base_url = settings.ECC_API_BASE_URL
        self.token = settings.ECC_API_TOKEN
        self.chunk_size = 100

    def fetch_articles_by_gtin(self, supplier_gtin_pairs: list[tuple[str, str]]) -> list[ArticleDataDTO]:
        """Fetches article data from ECC API using supplier GLN and GTIN pairs."""
        all_fetched_dtos = []
        if not self.token:
            raise APIError("ECC_API_TOKEN is not set in environment variables.")

        country_code = "de"  # Default country code
        params = {"token": self.token}

        for su_gln, ean in supplier_gtin_pairs:
            url = f"{self.base_url}/articleData/byEanAndSuGln/{ean}/{su_gln}/{country_code}"
            print(f"Get data for {ean} {su_gln}")

            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if "articles" in data and data["articles"]:
                    article_dtos = [ArticleDataDTO.from_api_response(item) for item in data["articles"]]
                    all_fetched_dtos.extend(article_dtos)
                else:
                    print(f"No articles found for EAN: {ean}, Supplier GLN: {su_gln}")

            except requests.exceptions.RequestException as e:
                print(f"API request failed for EAN {ean}, Supplier GLN {su_gln}: {e}")
                continue  # Continue with next pair instead of failing completely
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON response for EAN {ean}, Supplier GLN {su_gln}: {e}")
                continue

        return all_fetched_dtos

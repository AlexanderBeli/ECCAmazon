"""Client for the Global Stock API with batch processing and optimization."""

import concurrent.futures
import json
import logging
import time
from datetime import datetime
from threading import Lock
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.common.exceptions.custom_exceptions import APIError

logger = logging.getLogger(__name__)


class GlobalStockApiClient:
    def __init__(self) -> None:
        self.base_url = settings.EAN_AVAILABILITY_API_BASE_URL
        self.token = settings.EAN_AVAILABILITY_API_TOKEN
        self.retailer_gln = settings.RETAILER_GLN

        # Configure session with connection pooling and retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            # Change 'method_whitelist' to 'allowed_methods'
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Number of connection pools
            pool_maxsize=20,  # Maximum number of connections in each pool
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Thread-safe counter for progress tracking
        self._processed_count = 0
        self._lock = Lock()

    def get_gtins_with_stock(self, supplier_gln: str) -> list[str]:
        """
        Fetches a list of all GTINs (goods) with available stock for a given supplier.
        """
        if not self.token:
            raise APIError("EAN_AVAILABILITY_API_TOKEN is not set in environment variables.")

        url = f"{self.base_url}/supplierStockData/articlesWithStock/{supplier_gln}/{self.retailer_gln}"
        params = {"token": self.token}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            raise APIError(f"API request for GTINs with stock timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(
                f"Error fetching GTINs with stock from API: {e}. Status code: {e.response.status_code if e.response else 'N/A'}"
            )
        except json.JSONDecodeError as e:
            raise APIError(
                f"Failed to decode API JSON response for GTINs with stock: {e}. Raw response: {response.text if 'response' in locals() else 'N/A'}"
            )

    def get_gtin_availability(self, gtin: str, supplier_gln: str) -> dict:
        """
        Fetches detailed availability for a specific GTIN.
        Improved with session reuse and better error handling.
        """
        if not self.token:
            raise APIError("EAN_AVAILABILITY_API_TOKEN is not set in environment variables.")

        url = f"{self.base_url}/supplierStockData/availabilities/{gtin}"
        params = {
            "supplierGln": supplier_gln,
            "retailerGln": self.retailer_gln,
            "stockType": 1,
            "token": self.token,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning(f"⏳ Timeout for GTIN {gtin}")
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error for GTIN {gtin}: {e}")
            return {}

    def _process_gtin_batch(
        self, gtins_batch: list[str], supplier_gln: str, batch_num: int, total_batches: int
    ) -> list[GtinStockItemDTO]:
        """
        Processes a batch of GTINs and returns the stock items.
        This method is designed to be called in parallel.
        """
        fetched_items: list[GtinStockItemDTO] = []

        for gtin in gtins_batch:
            with self._lock:
                self._processed_count += 1
                current_count = self._processed_count

            logger.info(f"🔄 Batch {batch_num}/{total_batches} - Processing GTIN {current_count}: {gtin}")

            result = self.get_gtin_availability(gtin, supplier_gln)

            if "stocksQueryResult" not in result:
                continue

            for entry in result["stocksQueryResult"]:
                # Convert timestamp string to datetime object if it exists
                timestamp_str = entry.get("timestamp")
                timestamp_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else None

                fetched_items.append(
                    GtinStockItemDTO(
                        gtin=entry.get("gtin"),
                        quantity=entry.get("quantity"),
                        stock_traffic_light=entry.get("stockTrafficLight"),
                        item_type="Pair" if entry.get("type") == 1 else "Set",
                        timestamp=timestamp_dt,
                    )
                )

            # Small delay to avoid overwhelming the API
            time.sleep(0.1)

        return fetched_items

    def fetch_gtin_stock_data_optimized(
        self,
        supplier_context: SupplierContextDTO,
        batch_size: int = 100,
        max_workers: int = 5,
        save_callback: Optional[callable] = None,
    ) -> GtinStockResponseDTO:
        """
        Optimized version that processes GTINs in batches with optional concurrent processing
        and periodic saving to prevent data loss.
        """
        logger.info(f"📦 Starting optimized stock query for: {supplier_context.supplier_name}")

        gtins = self.get_gtins_with_stock(supplier_context.supplier_gln)
        total_gtins = len(gtins)

        logger.info(f"🔍 Fetching article details for {total_gtins} GTINs in batches of {batch_size}...")

        # Reset processed counter
        self._processed_count = 0
        all_fetched_items: list[GtinStockItemDTO] = []

        # Split GTINs into batches
        gtin_batches = [gtins[i : i + batch_size] for i in range(0, total_gtins, batch_size)]
        total_batches = len(gtin_batches)

        if max_workers == 1:
            # Sequential processing for better API rate limiting control
            for batch_num, batch_gtins in enumerate(gtin_batches, 1):
                logger.info(f"📝 Processing batch {batch_num}/{total_batches} ({len(batch_gtins)} GTINs)")

                batch_items = self._process_gtin_batch(
                    batch_gtins, supplier_context.supplier_gln, batch_num, total_batches
                )
                all_fetched_items.extend(batch_items)

                # Save intermediate results if callback provided
                if save_callback and batch_items:
                    try:
                        save_callback(supplier_context, batch_items)
                        logger.info(f"💾 Saved batch {batch_num} ({len(batch_items)} items)")
                    except Exception as e:
                        logger.error(f"⚠️ Failed to save batch {batch_num}: {e}")

                # Brief pause between batches
                if batch_num < total_batches:
                    time.sleep(1)
        else:
            # Concurrent processing (use with caution to not overwhelm API)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self._process_gtin_batch, batch_gtins, supplier_context.supplier_gln, batch_num, total_batches
                    ): batch_num
                    for batch_num, batch_gtins in enumerate(gtin_batches, 1)
                }

                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_num = future_to_batch[future]
                    try:
                        batch_items = future.result()
                        all_fetched_items.extend(batch_items)

                        # Save intermediate results if callback provided
                        if save_callback and batch_items:
                            try:
                                save_callback(supplier_context, batch_items)
                                logger.info(f"💾 Saved batch {batch_num} ({len(batch_items)} items)")
                            except Exception as e:
                                logger.error(f"⚠️ Failed to save batch {batch_num}: {e}")

                    except Exception as exc:
                        logger.error(f"❌ Batch {batch_num} generated an exception: {exc}")

        logger.info(
            f"✅ Stock query completed. Processed {total_gtins} GTINs, found {len(all_fetched_items)} stock items."
        )
        return GtinStockResponseDTO(supplier_context=supplier_context, stock_items=all_fetched_items)

    def fetch_gtin_stock_data(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """
        Legacy method for backward compatibility.
        Now delegates to the optimized version with default parameters.
        """
        return self.fetch_gtin_stock_data_optimized(
            supplier_context=supplier_context, batch_size=100, max_workers=1  # Sequential processing by default
        )

    def __del__(self) -> None:
        """Clean up the session when the object is destroyed."""
        if hasattr(self, "session"):
            self.session.close()

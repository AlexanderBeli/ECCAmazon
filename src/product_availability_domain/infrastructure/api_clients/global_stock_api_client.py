"""Client for the Global Stock API."""

import requests
import json
import time
from datetime import datetime

from src.common.config.settings import settings
from src.common.exceptions.custom_exceptions import APIError
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO


class GlobalStockApiClient:
    def __init__(self) -> None:
        self.base_url = settings.EAN_AVAILABILITY_API_BASE_URL
        self.token = settings.EAN_AVAILABILITY_API_TOKEN
        self.retailer_gln = settings.RETAILER_GLN

    def get_gtins_with_stock(self, supplier_gln: str) -> list[str]:
        """
        Fetches a list of all GTINs (goods) with available stock for a given supplier.
        """
        if not self.token:
            raise APIError("EAN_AVAILABILITY_API_TOKEN is not set in environment variables.")

        url = f"{self.base_url}/supplierStockData/articlesWithStock/{supplier_gln}/{self.retailer_gln}"
        params = {"token": self.token}

        try:
            response = requests.get(url, params=params, timeout=30)
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
        Includes retry logic for timeouts.
        """
        if not self.token:
            raise APIError("EAN_AVAILABILITY_API_TOKEN is not set in environment variables.")

        url = f"{self.base_url}/supplierStockData/availabilities/{gtin}"
        params = {
            "supplierGln": supplier_gln,
            "retailerGln": self.retailer_gln,
            "stockType": 1,  # As per the provided logic
            "token": self.token,
        }

        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                print(f"⏳ Timeout for GTIN {gtin}, attempt {attempt + 1}/3")
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                print(f"❌ Error for GTIN {gtin}: {e}")
                return {}  # Return empty dict on non-timeout request errors

        return {}  # Return empty dict if all attempts fail

    def fetch_gtin_stock_data(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """
        Orchestrates fetching all GTIN stock data for a given supplier context.
        """
        print(f"📦 Starting stock query for: {supplier_context.supplier_name}")

        gtins = self.get_gtins_with_stock(supplier_context.supplier_gln)

        print(f"🔍 Fetching article details for {len(gtins)} GTINs...")

        fetched_items: list[GtinStockItemDTO] = []
        for idx, gtin in enumerate(gtins, 1):
            print(f"🔄 ({idx}/{len(gtins)}) GTIN: {gtin}")
            result = self.get_gtin_availability(gtin, supplier_context.supplier_gln)

            if "stocksQueryResult" not in result:
                continue

            for entry in result["stocksQueryResult"]:
                # Convert timestamp string to datetime object if it exists
                timestamp_str = entry.get("timestamp")
                timestamp_dt = (
                    datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else None
                )  # Handle 'Z' for UTC

                fetched_items.append(
                    GtinStockItemDTO(
                        gtin=entry.get("gtin"),
                        quantity=entry.get("quantity"),
                        stock_traffic_light=entry.get("stockTrafficLight"),
                        item_type="Pair" if entry.get("type") == 1 else "Set",  # Convert type to string
                        timestamp=timestamp_dt,
                    )
                )
            time.sleep(0.2)  # Delay as in original logic

        print("✅ Stock query completed.")
        return GtinStockResponseDTO(supplier_context=supplier_context, stock_items=fetched_items)

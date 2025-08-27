"""Data Transfer Objects for Article data."""

import dataclasses
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ArticleDataDTO:
    eccId: int
    ean: Optional[str] = None
    mainArticleEccId: Optional[int] = None
    suGln: Optional[str] = None
    mfGln: Optional[str] = None
    suArticleNumber: Optional[str] = None
    mfArticleNumber: Optional[str] = None
    brandOriginal: Optional[str] = None
    brandCleared: Optional[str] = None
    modelName: Optional[str] = None
    articleName: Optional[str] = None
    catalogId: Optional[int] = None
    catalogName: Optional[str] = None
    dateChanged: Optional[str] = None
    status: Optional[int] = None
    textShort: Optional[str] = None
    textLong: Optional[str] = None
    textHtml: Optional[str] = None
    seasonEccId: Optional[int] = None
    seasonName: Optional[str] = None
    seasonDateFrom: Optional[str] = None
    seasonDateTo: Optional[str] = None
    gender: Optional[str] = None
    ageGroup: Optional[str] = None
    productCategoryEccId: Optional[int] = None
    productCategoryName: Optional[str] = None
    productGroupEccId: Optional[int] = None
    productGroupName: Optional[str] = None
    productSubGroupEccId: Optional[int] = None
    productSubGroupName: Optional[str] = None
    productFamilyEccId: Optional[int] = None
    productFamilyName: Optional[str] = None
    pricePricat: Optional[float] = None
    priceRetail: Optional[float] = None
    priceBase: Optional[float] = None
    taxClass: Optional[str] = None
    tax: Optional[int] = None
    currency: Optional[str] = None
    countryIso: Optional[str] = None
    originCountry: Optional[str] = None

    colorCode: Optional[str] = None
    colorName: Optional[str] = None
    easColor: Optional[str] = None
    customsTariffNumber: Optional[str] = None
    deliveryFrom: Optional[str] = None
    shoeWidth: Optional[str] = None
    materialName: Optional[str] = None
    innerMaterial: Optional[str] = None
    orgColor: Optional[str] = None
    images: list = field(default_factory=list)

    size: Optional[str] = None
    eccSizeId: Optional[int] = None
    sizeOriginal: Optional[str] = None
    sortIdx: Optional[int] = None
    sizeOrderQuantity: Optional[int] = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any], ean: str) -> "ArticleDataDTO":
        """Creates ArticleDataDTO from API response with new structure."""
        # Map API fields to DTO fields
        mapped_data = {
            "ean": ean,
            "eccId": data.get("eccId"),
            "suGln": data.get("suGln"),
            "mfGln": data.get("mfGln"),
            "suArticleNumber": data.get("suArticleNumber"),
            "mfArticleNumber": data.get("mfArticleNumber"),
            "brandOriginal": data.get("brand"),
            "brandCleared": data.get("brand"),
            "modelName": data.get("model"),
            "articleName": data.get("articleName"),
            "currency": data.get("currency"),
            "seasonName": data.get("seasonTxt"),
            # Добавленные поля
            "colorCode": data.get("colorCode"),
            "colorName": data.get("colorName"),
            "customsTariffNumber": data.get("customsTariffNumber"),
            "tax": data.get("tax"),
            "deliveryFrom": str(data.get("deliveryFrom")) if data.get("deliveryFrom") else None,  # Преобразуем в строку
            "shoeWidth": data.get("shoeWidth"),
            "materialName": data.get("materialName"),
            "innerMaterial": data.get("innerMaterial"),
            "orgColor": data.get("orgColor"),
        }

        # Check PRIMARY KEY
        if not mapped_data.get("ean") or not mapped_data.get("suGln"):
            logger.error(f"Missing required fields: ean={mapped_data.get('ean')}, suGln={mapped_data.get('suGln')}")
            raise ValueError(f"EAN and suGln are required for PRIMARY KEY")

        # Handle season data
        if data.get("season") and isinstance(data["season"], dict):
            mapped_data["seasonEccId"] = data["season"].get("id")
            mapped_data["seasonName"] = data["season"].get("value")

        # Handle easColor
        if data.get("easColor") and isinstance(data["easColor"], dict):
            mapped_data["easColor"] = data["easColor"].get("value")

        # Handle originCountry
        if data.get("originCountry") and isinstance(data["originCountry"], dict):
            mapped_data["originCountry"] = data["originCountry"].get("value")

        # Extract EAN data from assortment if available
        if data.get("assortment") and data["assortment"].get("de"):
            assortment_items = data["assortment"]["de"]

            found_item = next((item for item in assortment_items if item.get("ean") == ean), None)

            if not found_item and assortment_items:
                logger.warning(f"EAN {ean} not found in assortment, using first item")
                found_item = assortment_items[0]  # Fallback to first item

            if found_item:
                mapped_data.update(
                    {
                        "size": found_item.get("sizeCleared"),
                        "pricePricat": found_item.get("primeCost"),
                        "priceRetail": found_item.get("retailPrice"),
                        "eccSizeId": found_item.get("eccSizeId"),
                        "sizeOriginal": found_item.get("sizeOriginal"),
                        "sortIdx": found_item.get("sortIdx"),
                        "sizeOrderQuantity": found_item.get("sizeOrderQuantity"),
                    }
                )
            else:
                logger.warning(f"No assortment data found for EAN {ean}")

        # Handle images - extract all file URLs from media
        images = []

        # imageNameWwsImport if exist
        if data.get("imageNameWwsImport"):
            images.append(data["imageNameWwsImport"])

        if data.get("images"):
            for img_group in data["images"]:
                if img_group.get("media"):
                    for media_item in img_group["media"]:
                        file_url = media_item.get("file")
                        if file_url:
                            images.append(file_url)

        mapped_data["images"] = images

        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {
            k: v
            for k, v in mapped_data.items()
            if k in valid_keys and (k in ["ean", "suGln", "images"] or v is not None)
        }

        # logger.info(f"Mapped data keys: {list(filtered_data.keys())}")
        logger.info(f"EAN: {filtered_data.get('ean')}, suGln: {filtered_data.get('suGln')}")

        return cls(**filtered_data)

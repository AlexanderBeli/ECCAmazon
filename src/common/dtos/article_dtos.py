"""Data Transfer Objects for Article data."""

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional


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
    currency: Optional[str] = None
    countryIso: Optional[str] = None
    originCountry: Optional[str] = None

    colorCode: Optional[str] = None
    colorName: Optional[str] = None
    easColor: Optional[str] = None
    customsTariffNumber: Optional[str] = None
    tax: Optional[int] = None
    shoeWidth: Optional[str] = None
    innerMaterial: Optional[str] = None
    orgColor: Optional[str] = None
    images: list = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "ArticleDataDTO":
        """Creates ArticleDataDTO from API response with new structure."""
        # Map API fields to DTO fields
        mapped_data = {
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
            "shoeWidth": data.get("shoeWidth"),
            "innerMaterial": data.get("innerMaterial"),
            "orgColor": data.get("orgColor"),
        }

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

        # Extract EAN from assortment if available
        if data.get("assortment") and data["assortment"].get("de"):
            assortment_items = data["assortment"]["de"]
            if assortment_items and len(assortment_items) > 0:
                mapped_data["ean"] = assortment_items[0].get("ean")
                # Get pricing from first item
                mapped_data["pricePricat"] = assortment_items[0].get("primeCost")
                mapped_data["priceRetail"] = assortment_items[0].get("retailPrice")

        # Handle images - extract all file URLs from media
        images = []
        if data.get("images"):
            for img_group in data["images"]:
                if img_group.get("media"):
                    for i, media_item in enumerate(img_group["media"]):
                        file_url = media_item.get("file")
                        if file_url:
                            images.append(file_url)

        # Filter out None values and keys not in ArticleDataDTO
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {
            k: v
            for k, v in mapped_data.items()
            if k in valid_keys and v is not None and k not in ["attributes", "images"]
        }

        return cls(**filtered_data)

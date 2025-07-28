"""Data Transfer Objects for Article data."""

from dataclasses import dataclass, field
import dataclasses
from typing import Optional, Any


@dataclass
class AttributeDTO:
    key: str
    value: Optional[str] = None
    unit: Optional[str] = None


@dataclass
class ImageDTO:
    url: str
    type: Optional[str] = None
    sortIndex: Optional[int] = None


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
    attributes: list[AttributeDTO] = field(default_factory=list)
    images: list[ImageDTO] = field(default_factory=list)

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
        }

        # Handle season data
        if data.get("season") and isinstance(data["season"], dict):
            mapped_data["seasonEccId"] = data["season"].get("id")
            mapped_data["seasonName"] = data["season"].get("value")

        # Extract EAN from assortment if available
        if data.get("assortment") and data["assortment"].get("de"):
            assortment_items = data["assortment"]["de"]
            if assortment_items and len(assortment_items) > 0:
                mapped_data["ean"] = assortment_items[0].get("ean")
                # Get pricing from first item
                mapped_data["pricePricat"] = assortment_items[0].get("primeCost")
                mapped_data["priceRetail"] = assortment_items[0].get("retailPrice")

        # Handle images
        images = []
        if data.get("images"):
            for img_group in data["images"]:
                if img_group.get("media"):
                    for media_item in img_group["media"]:
                        images.append(ImageDTO(url=media_item.get("file", ""), type="product_image", sortIndex=0))

        # Filter out None values and keys not in ArticleDataDTO
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {
            k: v
            for k, v in mapped_data.items()
            if k in valid_keys and v is not None and k not in ["attributes", "images"]
        }

        return cls(**filtered_data, attributes=[], images=images)

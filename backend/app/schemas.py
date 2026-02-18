import re
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

SUPPORTED_MARKETPLACE_PATTERNS = {
    "amazon": re.compile(r"(?:^|\.)amazon\.(?:in|com)$", re.IGNORECASE),
    "flipkart": re.compile(r"(?:^|\.)flipkart\.com$", re.IGNORECASE),
}


def detect_marketplace(url: str) -> Optional[str]:
    hostname = urlparse(url).hostname or ""
    for marketplace, pattern in SUPPORTED_MARKETPLACE_PATTERNS.items():
        if pattern.search(hostname):
            return marketplace
    return None


class PriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(..., description="Product URL from a supported marketplace")
    marketplace: Optional[str] = Field(default=None, description="Marketplace override")

    @field_validator("url")
    @classmethod
    def url_must_be_supported(cls, value: HttpUrl) -> HttpUrl:
        if detect_marketplace(str(value)) is None:
            raise ValueError("Unsupported marketplace URL. Allowed: Amazon, Flipkart")
        return value

    @field_validator("marketplace")
    @classmethod
    def marketplace_must_be_supported(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_MARKETPLACE_PATTERNS:
            raise ValueError("Unsupported marketplace. Allowed: amazon, flipkart")
        return normalized


class ProductResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    price: Optional[float] = None
    image_url: Optional[str] = None
    thumbnail_images: List[str] = Field(default_factory=list)
    source: str
    marketplace: str
    tracker_url: Optional[str] = None
    alternatives_count: int = 0
    alternatives: List["AlternativeOffer"] = Field(default_factory=list)
    status: str
    error: Optional[str] = None


class AlternativeOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seller: str
    price: Optional[float] = None
    price_display: str = "N/A"
    link: Optional[str] = None
    logo_url: Optional[str] = None


ProductResponse.model_rebuild()

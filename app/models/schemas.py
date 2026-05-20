from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Marketplace(str, Enum):
    DROPDAX = "dropdax"


class PeriodType(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    CUSTOM = "custom"


class SaleType(str, Enum):
    EXPIRED_AUCTION = "Expired Auction"
    DROPPED = "Dropped"
    PRIVATE_SELLER = "Private Seller"
    UNKNOWN = "Unknown"


class DomainSale(BaseModel):
    domain: str
    price: float
    sale_type: str
    venue: str
    extension: str
    report_date: date
    source_url: str
    marketplace: Marketplace = Marketplace.DROPDAX


class DailyReportSummary(BaseModel):
    report_date: date
    title: str
    total_sales: int
    total_volume: float
    average_price: float
    top_sale_domain: str | None = None
    top_sale_price: float | None = None
    top_sale_venue: str | None = None
    source_url: str
    sales_count_in_report: int = 0


class DailyReport(DailyReportSummary):
    top_five: list[DomainSale] = Field(default_factory=list)
    sales: list[DomainSale] = Field(default_factory=list)


class SalesQueryParams(BaseModel):
    marketplace: Marketplace = Marketplace.DROPDAX
    period: PeriodType = PeriodType.WEEK
    start_date: date | None = None
    end_date: date | None = None
    extensions: list[str] = Field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    venue: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    sort_by: Literal["price", "date", "domain"] = "price"
    sort_order: Literal["asc", "desc"] = "desc"

    @field_validator("extensions", mode="before")
    @classmethod
    def normalize_extensions(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [ext.strip().lower().lstrip(".") for ext in value.split(",") if ext.strip()]
        return [ext.strip().lower().lstrip(".") for ext in value if ext.strip()]


class SalesResponse(BaseModel):
    marketplace: Marketplace
    period: PeriodType
    start_date: date
    end_date: date
    extensions: list[str]
    total_records: int
    filtered_records: int
    total_volume: float
    average_price: float
    sales: list[DomainSale]


class ReportListResponse(BaseModel):
    marketplace: Marketplace
    total_reports: int
    reports: list[DailyReportSummary]


class ExtensionStats(BaseModel):
    extension: str
    count: int
    total_volume: float
    average_price: float
    top_sale: DomainSale | None = None


class StatsResponse(BaseModel):
    marketplace: Marketplace
    period: PeriodType
    start_date: date
    end_date: date
    total_sales: int
    total_volume: float
    average_price: float
    by_extension: list[ExtensionStats]
    by_venue: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    version: str
    marketplace: str

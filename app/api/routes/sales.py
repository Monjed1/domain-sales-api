from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    DailyReport,
    Marketplace,
    PeriodType,
    ReportListResponse,
    SalesQueryParams,
    SalesResponse,
    StatsResponse,
)
from app.services.sales_service import sales_service

router = APIRouter(prefix="/sales", tags=["Sales"])


def _build_params(
    marketplace: Marketplace,
    period: PeriodType,
    start_date: date | None,
    end_date: date | None,
    extensions: str | None,
    min_price: float | None,
    max_price: float | None,
    venue: str | None,
    limit: int,
    sort_by: str,
    sort_order: str,
) -> SalesQueryParams:
    return SalesQueryParams(
        marketplace=marketplace,
        period=period,
        start_date=start_date,
        end_date=end_date,
        extensions=extensions or "",
        min_price=min_price,
        max_price=max_price,
        venue=venue,
        limit=limit,
        sort_by=sort_by,  # type: ignore[arg-type]
        sort_order=sort_order,  # type: ignore[arg-type]
    )


@router.get("", response_model=SalesResponse, summary="Get domain sales with filters")
async def get_sales(
    marketplace: Marketplace = Query(Marketplace.DROPDAX, description="Data source marketplace"),
    period: PeriodType = Query(PeriodType.WEEK, description="Time window: day, week, month, or custom"),
    start_date: date | None = Query(None, description="Start date (required for custom period)"),
    end_date: date | None = Query(None, description="End date (required for custom period)"),
    extensions: str | None = Query(
        None,
        description="Comma-separated TLD filters, e.g. com,ai,io",
        examples=["com,ai"],
    ),
    min_price: float | None = Query(None, ge=0, description="Minimum sale price in USD"),
    max_price: float | None = Query(None, ge=0, description="Maximum sale price in USD"),
    venue: str | None = Query(None, description="Filter by marketplace venue, e.g. GoDaddy"),
    limit: int = Query(100, ge=1, le=10000, description="Maximum number of sales to return"),
    sort_by: str = Query("price", pattern="^(price|date|domain)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> SalesResponse:
    """
    Scrape and return domain sales from DropDax daily market reports.

    - **period=day**: single day (defaults to yesterday)
    - **period=week**: top sales across the last 7 days
    - **period=month**: last 30 days
    - **period=custom**: use start_date and end_date
    - **extensions**: filter by TLD (.com, .ai, .io, etc.)
    """
    params = _build_params(
        marketplace,
        period,
        start_date,
        end_date,
        extensions,
        min_price,
        max_price,
        venue,
        limit,
        sort_by,
        sort_order,
    )

    try:
        return await sales_service.get_sales(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/weekly-top", response_model=SalesResponse, summary="Top weekly domain sales")
async def get_weekly_top_sales(
    extensions: str | None = Query(None, description="Comma-separated TLD filters"),
    min_price: float | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=10000),
    end_date: date | None = Query(None, description="Week ending date (defaults to yesterday)"),
) -> SalesResponse:
    """Return the highest-priced domain sales from the last 7 days."""
    params = _build_params(
        Marketplace.DROPDAX,
        PeriodType.WEEK,
        None,
        end_date,
        extensions,
        min_price,
        None,
        None,
        limit,
        "price",
        "desc",
    )
    return await sales_service.get_weekly_top_sales(params)


@router.get("/daily/{report_date}", response_model=DailyReport, summary="Single day full report")
async def get_daily_report(report_date: date) -> DailyReport:
    """Fetch a complete daily DropDax market report including all parsed sales."""
    report = await sales_service.get_daily_report(report_date)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No DropDax daily report found for {report_date.isoformat()}",
        )
    return report


@router.get("/reports", response_model=ReportListResponse, summary="List available daily reports")
async def list_reports(
    marketplace: Marketplace = Query(Marketplace.DROPDAX),
    max_pages: int = Query(10, ge=1, le=20, description="Category pages to scan"),
) -> ReportListResponse:
    """List discovered DropDax daily market report URLs and summaries."""
    try:
        return await sales_service.list_reports(marketplace, max_pages=max_pages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/stats", response_model=StatsResponse, summary="Aggregated sales statistics")
async def get_stats(
    period: PeriodType = Query(PeriodType.WEEK),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    extensions: str | None = Query(None),
) -> StatsResponse:
    """Market stats grouped by extension and venue for the selected period."""
    params = _build_params(
        Marketplace.DROPDAX,
        period,
        start_date,
        end_date,
        extensions,
        None,
        None,
        None,
        500,
        "price",
        "desc",
    )
    try:
        return await sales_service.get_stats(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/extensions", response_model=list[str], summary="Available extensions in period")
async def get_extensions(
    period: PeriodType = Query(PeriodType.WEEK),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> list[str]:
    """List TLD extensions present in scraped sales for the given period."""
    params = _build_params(
        Marketplace.DROPDAX,
        period,
        start_date,
        end_date,
        None,
        None,
        None,
        None,
        500,
        "price",
        "desc",
    )
    try:
        return await sales_service.get_available_extensions(params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from __future__ import annotations

from datetime import date

from app.models.schemas import (
    DailyReport,
    DailyReportSummary,
    DomainSale,
    ExtensionStats,
    Marketplace,
    PeriodType,
    ReportListResponse,
    SalesQueryParams,
    SalesResponse,
    StatsResponse,
)
from app.scrapers.dropdax import (
    DropDaxScraper,
    filter_sales,
    resolve_date_range,
    sort_sales,
)


class SalesService:
    def __init__(self) -> None:
        self.dropdax = DropDaxScraper()

    async def get_sales(self, params: SalesQueryParams) -> SalesResponse:
        start_date, end_date = await self._resolve_period_dates(params)

        reports = await self._load_reports(params.marketplace, start_date, end_date)
        all_sales = [sale for report in reports for sale in report.sales]

        filtered = filter_sales(
            all_sales,
            params.extensions,
            params.min_price,
            params.max_price,
            params.venue,
        )
        sorted_sales = sort_sales(filtered, params.sort_by, params.sort_order)
        limited = sorted_sales[: params.limit]

        total_volume = sum(sale.price for sale in limited)
        average_price = round(total_volume / len(limited), 2) if limited else 0.0

        return SalesResponse(
            marketplace=params.marketplace,
            period=params.period,
            start_date=start_date,
            end_date=end_date,
            extensions=params.extensions,
            total_records=len(all_sales),
            filtered_records=len(filtered),
            total_volume=total_volume,
            average_price=average_price,
            sales=limited,
        )

    async def get_weekly_top_sales(self, params: SalesQueryParams) -> SalesResponse:
        weekly_params = params.model_copy(update={"period": PeriodType.WEEK, "sort_by": "price"})
        response = await self.get_sales(weekly_params)
        response.sales = response.sales[: params.limit]
        return response

    async def get_daily_report(self, report_date: date) -> DailyReport | None:
        reports = await self.dropdax.list_reports(max_pages=15)
        match = next((report for report in reports if report.report_date == report_date), None)
        if not match:
            return None
        return await self.dropdax.fetch_report(match.source_url)

    async def list_reports(
        self,
        marketplace: Marketplace,
        max_pages: int = 10,
    ) -> ReportListResponse:
        if marketplace != Marketplace.DROPDAX:
            raise ValueError(f"Unsupported marketplace: {marketplace}")

        reports = await self.dropdax.list_reports(max_pages=max_pages)
        return ReportListResponse(
            marketplace=marketplace,
            total_reports=len(reports),
            reports=reports,
        )

    async def get_stats(self, params: SalesQueryParams) -> StatsResponse:
        start_date, end_date = await self._resolve_period_dates(params)
        sales_response = await self.get_sales(
            params.model_copy(
                update={
                    "limit": 10000,
                    "sort_by": "price",
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
        )

        by_extension: dict[str, list[DomainSale]] = {}
        by_venue: dict[str, int] = {}

        for sale in sales_response.sales:
            by_extension.setdefault(sale.extension, []).append(sale)
            by_venue[sale.venue] = by_venue.get(sale.venue, 0) + 1

        extension_stats: list[ExtensionStats] = []
        for extension, items in sorted(by_extension.items(), key=lambda pair: -len(pair[1])):
            volume = sum(item.price for item in items)
            top_sale = max(items, key=lambda item: item.price)
            extension_stats.append(
                ExtensionStats(
                    extension=extension,
                    count=len(items),
                    total_volume=volume,
                    average_price=round(volume / len(items), 2),
                    top_sale=top_sale,
                )
            )

        total_volume = sum(sale.price for sale in sales_response.sales)
        total_sales = len(sales_response.sales)

        return StatsResponse(
            marketplace=params.marketplace,
            period=params.period,
            start_date=sales_response.start_date,
            end_date=sales_response.end_date,
            total_sales=total_sales,
            total_volume=total_volume,
            average_price=round(total_volume / total_sales, 2) if total_sales else 0.0,
            by_extension=extension_stats,
            by_venue=dict(sorted(by_venue.items(), key=lambda pair: -pair[1])),
        )

    async def get_available_extensions(
        self,
        params: SalesQueryParams,
    ) -> list[str]:
        sales_response = await self.get_sales(
            params.model_copy(update={"limit": 10000, "extensions": []})
        )
        extensions = sorted({sale.extension for sale in sales_response.sales})
        return extensions

    async def _load_reports(
        self,
        marketplace: Marketplace,
        start_date: date,
        end_date: date,
    ) -> list[DailyReport]:
        if marketplace != Marketplace.DROPDAX:
            raise ValueError(f"Unsupported marketplace: {marketplace}")
        return await self.dropdax.fetch_reports_for_range(start_date, end_date)

    async def _resolve_period_dates(self, params: SalesQueryParams) -> tuple[date, date]:
        latest_report_date: date | None = None
        if not params.end_date and params.period in {
            PeriodType.DAY,
            PeriodType.WEEK,
            PeriodType.MONTH,
        }:
            reports = await self.dropdax.list_reports(max_pages=2)
            if reports:
                latest_report_date = reports[0].report_date

        if params.period == PeriodType.DAY and not params.start_date and not params.end_date:
            if latest_report_date:
                return latest_report_date, latest_report_date

        return resolve_date_range(
            params.period.value,
            params.start_date,
            params.end_date or latest_report_date,
        )


sales_service = SalesService()

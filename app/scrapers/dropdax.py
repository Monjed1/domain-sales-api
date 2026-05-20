from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.cache import cache_key, cache_service
from app.core.config import get_settings
from app.models.schemas import DailyReport, DailyReportSummary, DomainSale, Marketplace

REPORT_LINK_PATTERN = re.compile(
    r"/blog/daily-domain-market-report-[a-z0-9-]+/?$",
    re.IGNORECASE,
)
SUMMARY_PATTERN = re.compile(
    r"recorded\s+([\d,]+)\s+sales\s+for\s+a\s+total\s+of\s+\$([\d,]+)",
    re.IGNORECASE,
)
AVG_PRICE_PATTERN = re.compile(
    r"average\s+sale\s+price\s+of\s+\$([\d,]+)",
    re.IGNORECASE,
)
TOP_SALE_PATTERN = re.compile(
    r"top\s+sale\s+of\s+the\s+day\s+was\s+([^\s]+)\s+which\s+sold\s+for\s+\$([\d,]+)\s+at\s+(.+?)\.",
    re.IGNORECASE,
)
DATE_IN_TITLE_PATTERN = re.compile(
    r"for\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)",
    re.IGNORECASE,
)
MULTI_PART_TLDS = {
    "co.uk",
    "org.uk",
    "com.au",
    "co.za",
    "co.jp",
    "com.br",
}


class DropDaxScraper:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.dropdax_base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str:
        async with self._semaphore:
            response = await client.get(url, headers=self._headers(), follow_redirects=True)
            if response.status_code == 404:
                raise httpx.HTTPStatusError(
                    "Not found",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.text

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str | None:
        async with self._semaphore:
            response = await client.get(url, headers=self._headers(), follow_redirects=True)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text

    async def list_reports(self, max_pages: int = 10) -> list[DailyReportSummary]:
        key = cache_key("dropdax", "reports", str(max_pages))
        return await cache_service.get_or_set(key, lambda: self._list_reports(max_pages))

    async def _list_reports(self, max_pages: int) -> list[DailyReportSummary]:
        reports: list[DailyReportSummary] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            for page in range(1, max_pages + 1):
                page_url = self._category_url(page)
                html = await self._fetch_page(client, page_url)
                if html is None:
                    break
                page_reports = self._parse_category_page(html)
                if not page_reports:
                    break

                for report in page_reports:
                    if report.source_url not in seen_urls:
                        seen_urls.add(report.source_url)
                        reports.append(report)

        reports.sort(key=lambda item: item.report_date, reverse=True)
        return reports

    def _category_url(self, page: int) -> str:
        path = self.settings.dropdax_category_path
        if page <= 1:
            return f"{self.base_url}{path}"
        return f"{self.base_url}{path}page/{page}/"

    def _parse_category_page(self, html: str) -> list[DailyReportSummary]:
        soup = BeautifulSoup(html, "lxml")
        reports: list[DailyReportSummary] = []

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not REPORT_LINK_PATTERN.search(href):
                continue

            title = link.get_text(" ", strip=True)
            if "Daily Market Report" not in title:
                continue

            source_url = urljoin(self.base_url, href)
            report_date = self._extract_date_from_title(title) or self._extract_date_from_url(href)
            summary = self._parse_category_title(title, report_date, source_url)
            if summary:
                reports.append(summary)

        return reports

    def _parse_category_title(
        self,
        title: str,
        report_date: date | None,
        source_url: str,
    ) -> DailyReportSummary | None:
        volume_match = re.search(r"\$([\d.]+[kKmM]?)\s+in\s+Sales", title)
        top_match = re.search(
            r"sold\s+for\s+\$([\d,]+)\s+at\s+([^–-]+)",
            title,
            re.IGNORECASE,
        )
        domain_match = re.search(r"–\s+([^\s]+)\s+sold\s+for", title)

        if not report_date:
            return None

        total_volume = self._parse_money(volume_match.group(1)) if volume_match else 0.0
        top_domain = domain_match.group(1).strip() if domain_match else None
        top_price = self._parse_price(top_match.group(1)) if top_match else None
        top_venue = top_match.group(2).strip() if top_match else None

        return DailyReportSummary(
            report_date=report_date,
            title=title,
            total_sales=0,
            total_volume=total_volume,
            average_price=0.0,
            top_sale_domain=top_domain,
            top_sale_price=top_price,
            top_sale_venue=top_venue,
            source_url=source_url,
        )

    async def fetch_report(self, source_url: str) -> DailyReport:
        key = cache_key("dropdax", "report", source_url)
        return await cache_service.get_or_set(key, lambda: self._fetch_report(source_url))

    async def _fetch_report(self, source_url: str) -> DailyReport:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            html = await self._fetch(client, source_url)
        return self._parse_report_page(html, source_url)

    async def fetch_reports_for_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list[DailyReport]:
        days = (end_date - start_date).days + 1
        max_pages = min(10, max(2, (days // 6) + 2))
        all_reports = await self._list_reports(max_pages=max_pages)
        selected = [
            report
            for report in all_reports
            if start_date <= report.report_date <= end_date
        ]

        tasks = [self._fetch_report(report.source_url) for report in selected]
        if not tasks:
            return []

        return await asyncio.gather(*tasks)

    def _parse_report_page(self, html: str, source_url: str) -> DailyReport:
        soup = BeautifulSoup(html, "lxml")
        title = self._extract_page_title(soup)
        report_date = (
            self._extract_date_from_title(title)
            or self._extract_date_from_url(source_url)
            or date.today()
        )

        intro = self._extract_intro_text(soup)
        summary = self._parse_intro_summary(intro, title, report_date, source_url)
        top_five = self._parse_top_five(soup, report_date, source_url)
        sales = self._parse_sales_table(soup, report_date, source_url)

        if summary.total_sales == 0 and sales:
            summary.total_sales = len(sales)
        if summary.total_volume == 0 and sales:
            summary.total_volume = sum(sale.price for sale in sales)
        if summary.average_price == 0 and sales:
            summary.average_price = round(summary.total_volume / len(sales), 2)

        summary.sales_count_in_report = len(sales)

        return DailyReport(
            **summary.model_dump(),
            top_five=top_five,
            sales=sales,
        )

    def _extract_page_title(self, soup: BeautifulSoup) -> str:
        heading = soup.select_one("h1")
        if heading:
            return heading.get_text(" ", strip=True)
        if soup.title:
            return soup.title.get_text(" ", strip=True)
        return ""

    def _extract_intro_text(self, soup: BeautifulSoup) -> str:
        article = soup.select_one("article") or soup.select_one(".entry-content") or soup.body
        if not article:
            return ""

        paragraphs = article.find_all("p", recursive=True)
        for paragraph in paragraphs[:5]:
            text = paragraph.get_text(" ", strip=True)
            if "recorded" in text.lower() and "sales" in text.lower():
                return text
        return paragraphs[0].get_text(" ", strip=True) if paragraphs else ""

    def _parse_intro_summary(
        self,
        intro: str,
        title: str,
        report_date: date,
        source_url: str,
    ) -> DailyReportSummary:
        total_sales = 0
        total_volume = 0.0
        average_price = 0.0
        top_domain = None
        top_price = None
        top_venue = None

        sales_match = SUMMARY_PATTERN.search(intro)
        if sales_match:
            total_sales = int(sales_match.group(1).replace(",", ""))
            total_volume = float(sales_match.group(2).replace(",", ""))

        avg_match = AVG_PRICE_PATTERN.search(intro)
        if avg_match:
            average_price = float(avg_match.group(1).replace(",", ""))

        top_match = TOP_SALE_PATTERN.search(intro)
        if top_match:
            top_domain = top_match.group(1).strip()
            top_price = float(top_match.group(2).replace(",", ""))
            top_venue = top_match.group(3).strip()

        if total_volume == 0:
            volume_match = re.search(r"\$([\d.]+[kKmM]?)\s+in\s+Sales", title)
            if volume_match:
                total_volume = self._parse_money(volume_match.group(1))

        return DailyReportSummary(
            report_date=report_date,
            title=title,
            total_sales=total_sales,
            total_volume=total_volume,
            average_price=average_price,
            top_sale_domain=top_domain,
            top_sale_price=top_price,
            top_sale_venue=top_venue,
            source_url=source_url,
        )

    def _parse_top_five(
        self,
        soup: BeautifulSoup,
        report_date: date,
        source_url: str,
    ) -> list[DomainSale]:
        sales: list[DomainSale] = []
        for heading in soup.find_all(["h2", "h3"]):
            if "top 5" not in heading.get_text(" ", strip=True).lower():
                continue

            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in {"h2", "h3"}:
                if sibling.name == "ul":
                    for item in sibling.find_all("li"):
                        sale = self._parse_list_item_sale(item, report_date, source_url)
                        if sale:
                            sales.append(sale)
                sibling = sibling.find_next_sibling()
            break
        return sales

    def _parse_list_item_sale(
        self,
        item: Tag,
        report_date: date,
        source_url: str,
    ) -> DomainSale | None:
        text = item.get_text(" ", strip=True)
        match = re.match(
            r"([^\s–-]+)\s*[–-]\s*\$([\d,]+)\s*\(([^)]+)\)",
            text,
        )
        if not match:
            return None

        domain = match.group(1).strip()
        return DomainSale(
            domain=domain,
            price=float(match.group(2).replace(",", "")),
            sale_type="Unknown",
            venue=match.group(3).strip(),
            extension=extract_extension(domain),
            report_date=report_date,
            source_url=source_url,
            marketplace=Marketplace.DROPDAX,
        )

    def _parse_sales_table(
        self,
        soup: BeautifulSoup,
        report_date: date,
        source_url: str,
    ) -> list[DomainSale]:
        sales: list[DomainSale] = []

        for table in soup.find_all("table"):
            headers = [cell.get_text(" ", strip=True).lower() for cell in table.find_all("th")]
            if not headers or "domain" not in headers[0]:
                continue

            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue

                domain = self._cell_domain(cells[0])
                price = self._cell_price(cells[1])
                if not domain or price is None:
                    continue

                sale_type = cells[2].get_text(" ", strip=True)
                venue = cells[3].get_text(" ", strip=True)

                sales.append(
                    DomainSale(
                        domain=domain,
                        price=price,
                        sale_type=sale_type or "Unknown",
                        venue=venue or "Unknown",
                        extension=extract_extension(domain),
                        report_date=report_date,
                        source_url=source_url,
                        marketplace=Marketplace.DROPDAX,
                    )
                )
            break

        return sales

    def _cell_domain(self, cell: Tag) -> str | None:
        link = cell.find("a")
        if link:
            text = link.get_text(" ", strip=True)
            if text:
                return text
        text = cell.get_text(" ", strip=True)
        return text or None

    def _cell_price(self, cell: Tag) -> float | None:
        text = cell.get_text(" ", strip=True)
        cleaned = text.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_date_from_title(self, title: str) -> date | None:
        patterns = [
            r"on\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)",
            r"for\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)",
            DATE_IN_TITLE_PATTERN,
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if not match:
                continue
            parsed = self._safe_parse_date(match.group(1))
            if parsed:
                return parsed
        return None

    def _extract_date_from_url(self, url: str) -> date | None:
        match = re.search(
            r"daily-domain-market-report-([a-z]+)-(\d{1,2})-(\d{4})",
            url,
            re.IGNORECASE,
        )
        if not match:
            return None
        month_name, day, year = match.groups()
        try:
            parsed = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
            return parsed.date()
        except ValueError:
            return self._safe_parse_date(f"{month_name} {day} {year}")

    def _safe_parse_date(self, value: str) -> date | None:
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", value.strip(), flags=re.IGNORECASE)
        try:
            parsed = date_parser.parse(cleaned, default=datetime(2026, 1, 1))
            return parsed.date()
        except (ValueError, TypeError):
            return None

    def _parse_price(self, value: str) -> float:
        return float(value.replace("$", "").replace(",", "").strip())

    def _parse_money(self, value: str) -> float:
        cleaned = value.replace("$", "").replace(",", "").strip().lower()
        multiplier = 1.0
        if cleaned.endswith("k"):
            multiplier = 1_000.0
            cleaned = cleaned[:-1]
        elif cleaned.endswith("m"):
            multiplier = 1_000_000.0
            cleaned = cleaned[:-1]
        return float(cleaned) * multiplier


def extract_extension(domain: str) -> str:
    domain = domain.strip().lower()
    parts = domain.split(".")
    if len(parts) < 2:
        return domain

    candidate = ".".join(parts[-2:])
    if candidate in MULTI_PART_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return parts[-1]


def resolve_date_range(
    period: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    today = date.today()
    if period == "day":
        target = end_date or today - timedelta(days=1)
        return target, target
    if period == "week":
        end = end_date or today - timedelta(days=1)
        start = start_date or (end - timedelta(days=6))
        return start, end
    if period == "month":
        end = end_date or today - timedelta(days=1)
        start = start_date or (end - timedelta(days=29))
        return start, end
    if period == "custom":
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required for custom period")
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        return start_date, end_date
    raise ValueError(f"Unsupported period: {period}")


def filter_sales(
    sales: Iterable[DomainSale],
    extensions: list[str],
    min_price: float | None,
    max_price: float | None,
    venue: str | None,
) -> list[DomainSale]:
    filtered: list[DomainSale] = []
    for sale in sales:
        if extensions and sale.extension.lower() not in extensions:
            continue
        if min_price is not None and sale.price < min_price:
            continue
        if max_price is not None and sale.price > max_price:
            continue
        if venue and venue.lower() not in sale.venue.lower():
            continue
        filtered.append(sale)
    return filtered


def sort_sales(
    sales: list[DomainSale],
    sort_by: str,
    sort_order: str,
) -> list[DomainSale]:
    reverse = sort_order == "desc"
    if sort_by == "price":
        return sorted(sales, key=lambda item: item.price, reverse=reverse)
    if sort_by == "date":
        return sorted(sales, key=lambda item: item.report_date, reverse=reverse)
    return sorted(sales, key=lambda item: item.domain.lower(), reverse=reverse)

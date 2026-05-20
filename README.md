# Domain Sales Scraper API

Production-ready REST API that scrapes daily domain sales data from [DropDax](https://dropdax.com/) daily market reports. Filter by **extension**, **time period**, **price**, and **venue**.

## Features

- Scrape DropDax daily market reports (top 150+ sales per day)
- Filter by TLD extension (`.com`, `.ai`, `.io`, etc.)
- Time periods: `day`, `week`, `month`, or custom date range
- Weekly top sales endpoint
- Aggregated stats by extension and venue
- Response caching (1 hour default)
- OpenAPI docs at `/docs`
- Docker-ready deployment

## Quick Start (Docker)

```bash
docker compose up --build
```

API available at: http://localhost:7852  
Interactive docs: http://localhost:7852/docs

## Local Development

Requires Python 3.11+.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 7852
```

## Deploy to GitHub & VPS

See **[DEPLOY.md](DEPLOY.md)** for pushing to GitHub and deploying on a VPS (port **7852**).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/sales` | Sales with filters |
| GET | `/api/v1/sales/weekly-top` | Top weekly sales by price |
| GET | `/api/v1/sales/daily/{date}` | Full single-day report |
| GET | `/api/v1/sales/reports` | List available report dates |
| GET | `/api/v1/sales/stats` | Aggregated market stats |
| GET | `/api/v1/sales/extensions` | Available TLDs in period |

## Example Requests

### Top .com sales this week

```
GET /api/v1/sales?period=week&extensions=com&limit=20&sort_by=price&sort_order=desc
```

### .ai sales in a custom date range

```
GET /api/v1/sales?period=custom&start_date=2026-05-01&end_date=2026-05-07&extensions=ai
```

### Top weekly sales (all extensions)

```
GET /api/v1/sales/weekly-top?limit=50
```

### Full daily report

```
GET /api/v1/sales/daily/2026-05-06
```

### Stats by extension for the last month

```
GET /api/v1/sales/stats?period=month
```

## Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `week` | `day`, `week`, `month`, `custom` |
| `start_date` | date | — | Required when `period=custom` |
| `end_date` | date | — | Required when `period=custom` |
| `extensions` | string | — | Comma-separated TLDs: `com,ai,io` |
| `min_price` | float | — | Minimum USD price |
| `max_price` | float | — | Maximum USD price |
| `venue` | string | — | e.g. `GoDaddy`, `Namecheap` |
| `limit` | int | 100 | Max results (1–500) |
| `sort_by` | string | `price` | `price`, `date`, `domain` |
| `sort_order` | string | `desc` | `asc` or `desc` |

## Response Example

```json
{
  "marketplace": "dropdax",
  "period": "week",
  "start_date": "2026-05-12",
  "end_date": "2026-05-18",
  "extensions": ["com"],
  "total_records": 4200,
  "filtered_records": 3100,
  "total_volume": 1250000.0,
  "average_price": 403.22,
  "sales": [
    {
      "domain": "example.com",
      "price": 25000.0,
      "sale_type": "Expired Auction",
      "venue": "GoDaddy",
      "extension": "com",
      "report_date": "2026-05-18",
      "source_url": "https://dropdax.com/blog/...",
      "marketplace": "dropdax"
    }
  ]
}
```

## Architecture

```
app/
├── main.py              # FastAPI application
├── api/routes/          # HTTP endpoints
├── scrapers/dropdax.py  # DropDax HTML scraper
├── services/            # Business logic & aggregation
├── models/schemas.py    # Pydantic models
└── core/                # Config & caching
```

Data is sourced from DropDax blog daily reports. Each report includes summary stats, top 5 sales, and a table of up to 150 top sales for that day. The API discovers reports from the [Daily Market Reports](https://dropdax.com/blog/category/daily-market-reports/) category and parses HTML tables.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Debug mode |
| `CACHE_TTL_SECONDS` | `3600` | Cache lifetime |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout (seconds) |

## Notes

- DropDax publishes one report per trading day; `period=week` aggregates up to 7 daily reports.
- The main DropDax data engine (`dropdax.com/?date=...`) is Cloudflare-protected; this API uses publicly accessible blog reports.
- Respect DropDax terms of service and use reasonable request rates (built-in caching and concurrency limits).
- Additional marketplaces can be added by implementing new scrapers under `app/scrapers/`.

## License

MIT

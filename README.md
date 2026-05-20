# Domain Sales Scraper API

Production-ready REST API that scrapes daily domain sales data from [DropDax](https://dropdax.com/) daily market reports. Filter by **extension**, **time period**, **price**, and **venue**.

**Base URL (local):** `http://localhost:7852`  
**Base URL (VPS):** `http://YOUR_VPS_IP:7852`  
**Interactive docs:** `/docs`  
**OpenAPI JSON:** `/openapi.json`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [How to Use (Detailed Guide)](#how-to-use-detailed-guide)
3. [API Reference](#api-reference)
4. [Query Parameters](#query-parameters)
5. [Response Fields](#response-fields)
6. [Common Use Cases](#common-use-cases)
7. [Using with n8n](#using-with-n8n)
8. [Deploy to GitHub & VPS](#deploy-to-github--vps)
9. [Configuration](#configuration)
10. [Architecture](#architecture)

---

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

- API: http://localhost:7852  
- Docs: http://localhost:7852/docs  

### Local (Python 3.11+)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env    # Windows
# cp .env.example .env    # macOS / Linux

uvicorn app.main:app --reload --host 0.0.0.0 --port 7852
```

### Verify it works

```bash
curl http://localhost:7852/api/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "marketplace": "dropdax"
}
```

---

## How to Use (Detailed Guide)

### Step 1 — Open the interactive docs

The easiest way to explore the API is Swagger UI:

1. Start the server (Docker or `uvicorn`).
2. Open **http://localhost:7852/docs** in your browser.
3. Click any endpoint → **Try it out** → set parameters → **Execute**.

You can also use **http://localhost:7852/redoc** for readable documentation.

---

### Step 2 — Understand time periods

Sales are grouped by **report date** (the day DropDax published the market report, e.g. “sales on May 18th”).

| `period` value | What you get | Default date range |
|----------------|--------------|-------------------|
| `day` | Latest single daily report | Most recent report on DropDax |
| `week` | Up to 7 days of reports | Last 7 report days ending at latest report |
| `month` | Up to 30 days of reports | Last 30 report days |
| `custom` | Your range | Requires `start_date` and `end_date` (`YYYY-MM-DD`) |

**Important:** Dates are **sale report dates**, not “today.” DropDax usually publishes a report one day after the trading day.

---

### Step 3 — Filter by extension (TLD)

Use the `extensions` query parameter with comma-separated TLDs **without the dot**:

| You want | Parameter |
|----------|-----------|
| `.com` only | `extensions=com` |
| `.ai` and `.io` | `extensions=ai,io` |
| All extensions | omit `extensions` |

Examples:

```bash
# Top .com sales this week
curl "http://localhost:7852/api/v1/sales?period=week&extensions=com&limit=10"

# .ai sales in May 2026 (custom range)
curl "http://localhost:7852/api/v1/sales?period=custom&start_date=2026-05-01&end_date=2026-05-18&extensions=ai"
```

**PowerShell (Windows):**

```powershell
Invoke-RestMethod "http://localhost:7852/api/v1/sales?period=week&extensions=com&limit=5" |
  Select-Object -ExpandProperty sales |
  Format-Table domain, price, venue
```

---

### Step 4 — Main endpoint: search sales

**Endpoint:** `GET /api/v1/sales`

This is the primary endpoint. It scrapes DropDax reports for your date range, merges sales, applies filters, sorts, and returns up to `limit` results.

**Minimal example (latest day, all extensions):**

```bash
curl "http://localhost:7852/api/v1/sales?period=day&limit=5"
```

**Full example (week, .com, min $5,000, sorted by price):**

```bash
curl "http://localhost:7852/api/v1/sales?period=week&extensions=com&min_price=5000&limit=20&sort_by=price&sort_order=desc"
```

**Filter by venue (marketplace where the domain sold):**

```bash
curl "http://localhost:7852/api/v1/sales?period=week&venue=GoDaddy&limit=15"
```

Common venues: `GoDaddy`, `Namecheap`, `DropCatch`, `Sedo`, `Afternic`, `Dynadot`, `Atom.com`.

---

### Step 5 — Weekly top sales

**Endpoint:** `GET /api/v1/sales/weekly-top`

Shortcut for the highest-priced sales in the last 7 report days (always sorted by price, descending).

```bash
# Top 20 sales of the week (all TLDs)
curl "http://localhost:7852/api/v1/sales/weekly-top?limit=20"

# Top weekly .ai sales
curl "http://localhost:7852/api/v1/sales/weekly-top?extensions=ai&limit=10"
```

---

### Step 6 — Full report for one day

**Endpoint:** `GET /api/v1/sales/daily/{date}`

Returns the complete parsed report for one date: summary, top 5, and up to ~150 sales from the DropDax table.

```bash
curl "http://localhost:7852/api/v1/sales/daily/2026-05-18"
```

Response includes:

- `total_sales`, `total_volume`, `average_price` — day summary  
- `top_five` — quick recap list  
- `sales` — full sales table  

Use this when you need **everything** for one day, not a filtered subset.

---

### Step 7 — List available report dates

**Endpoint:** `GET /api/v1/sales/reports`

Discover which daily reports exist before querying a specific date.

```bash
curl "http://localhost:7852/api/v1/sales/reports"
```

Each item has `report_date`, `title`, `source_url`, and partial summary (`total_volume`, top sale info).

---

### Step 8 — Market statistics

**Endpoint:** `GET /api/v1/sales/stats`

Aggregated breakdown for a period: totals plus groups by extension and venue.

```bash
curl "http://localhost:7852/api/v1/sales/stats?period=week"
curl "http://localhost:7852/api/v1/sales/stats?period=month&extensions=com"
```

Useful fields:

- `by_extension` — count, volume, average price, top sale per TLD  
- `by_venue` — how many sales per marketplace  

---

### Step 9 — List extensions in a period

**Endpoint:** `GET /api/v1/sales/extensions`

Returns all TLDs that appear in scraped sales for the period (helps you know what to filter).

```bash
curl "http://localhost:7852/api/v1/sales/extensions?period=week"
```

Example response:

```json
["ai", "app", "co", "com", "io", "net", "org", "xyz"]
```

---

### Step 10 — Sorting and limits

| Parameter | Values | Default | Use when |
|-----------|--------|---------|----------|
| `sort_by` | `price`, `date`, `domain` | `price` | You want cheapest, alphabetical, etc. |
| `sort_order` | `asc`, `desc` | `desc` | Ascending vs descending |
| `limit` | 1–10000 | 100 | Control response size |

```bash
# Cheapest .com sales this week
curl "http://localhost:7852/api/v1/sales?period=week&extensions=com&sort_by=price&sort_order=asc&limit=10"

# Domains A→Z
curl "http://localhost:7852/api/v1/sales?period=day&sort_by=domain&sort_order=asc&limit=50"
```

---

### Using from JavaScript (fetch)

```javascript
const base = "http://localhost:7852";

const res = await fetch(
  `${base}/api/v1/sales?period=week&extensions=com&limit=10`
);
const data = await res.json();

data.sales.forEach((sale) => {
  console.log(`${sale.domain} — $${sale.price} @ ${sale.venue}`);
});
```

---

### Using from Python (requests)

```python
import requests

BASE = "http://localhost:7852"

response = requests.get(
    f"{BASE}/api/v1/sales",
    params={
        "period": "week",
        "extensions": "com,ai",
        "min_price": 1000,
        "limit": 25,
        "sort_by": "price",
    },
    timeout=60,
)
response.raise_for_status()
data = response.json()

print(f"Found {data['filtered_records']} sales")
for sale in data["sales"]:
    print(f"{sale['domain']:30} ${sale['price']:>10,.0f}  {sale['venue']}")
```

---

### Errors and status codes

| Code | Meaning | Typical cause |
|------|---------|---------------|
| `200` | Success | — |
| `400` | Bad request | `period=custom` without dates, invalid dates |
| `404` | Not found | No DropDax report for `daily/{date}` |
| `500` | Server error | DropDax unreachable; retry later |

First request for a date range may take **10–30 seconds** (scraping + cache). Later requests are faster (1-hour cache).

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info and doc links |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/sales` | Sales with filters |
| GET | `/api/v1/sales/weekly-top` | Top weekly sales by price |
| GET | `/api/v1/sales/daily/{date}` | Full single-day report (`YYYY-MM-DD`) |
| GET | `/api/v1/sales/reports` | List available report dates |
| GET | `/api/v1/sales/stats` | Aggregated market stats |
| GET | `/api/v1/sales/extensions` | Available TLDs in period |

---

## Query Parameters

### `/api/v1/sales`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `marketplace` | string | `dropdax` | Data source (currently only `dropdax`) |
| `period` | string | `week` | `day`, `week`, `month`, `custom` |
| `start_date` | date | — | Required when `period=custom` (`YYYY-MM-DD`) |
| `end_date` | date | — | Required when `period=custom` |
| `extensions` | string | — | Comma-separated TLDs: `com,ai,io` |
| `min_price` | float | — | Minimum USD price |
| `max_price` | float | — | Maximum USD price |
| `venue` | string | — | Partial match, e.g. `GoDaddy` |
| `limit` | int | 100 | Max results (1–10000) |
| `sort_by` | string | `price` | `price`, `date`, `domain` |
| `sort_order` | string | `desc` | `asc` or `desc` |

### `/api/v1/sales/weekly-top`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `extensions` | string | — | Comma-separated TLDs |
| `min_price` | float | — | Minimum USD price |
| `limit` | int | 50 | Max results (1–10000) |
| `end_date` | date | — | Week ending date (defaults to latest report) |

### `/api/v1/sales/stats` and `/api/v1/sales/extensions`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `week` | `day`, `week`, `month`, `custom` |
| `start_date` | date | — | For `custom` period |
| `end_date` | date | — | For `custom` period |
| `extensions` | string | — | Stats only: filter before aggregating |

---

## Response Fields

### Single sale object

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | Full domain name, e.g. `example.com` |
| `price` | float | Sale price in USD |
| `sale_type` | string | e.g. `Expired Auction`, `Dropped`, `Private Seller` |
| `venue` | string | Marketplace where it sold |
| `extension` | string | TLD without dot, e.g. `com`, `ai` |
| `report_date` | date | Date of the DropDax daily report |
| `source_url` | string | Link to the blog report |
| `marketplace` | string | Always `dropdax` for now |

### Sales list response (`/api/v1/sales`)

| Field | Description |
|-------|-------------|
| `total_records` | All sales scraped in range (before extension/price filters) |
| `filtered_records` | Count after your filters |
| `total_volume` | Sum of `price` in returned `sales` array |
| `average_price` | Average of returned `sales` |
| `start_date` / `end_date` | Actual range used |
| `extensions` | Extensions you filtered by (empty = all) |

### Example response

```json
{
  "marketplace": "dropdax",
  "period": "week",
  "start_date": "2026-05-12",
  "end_date": "2026-05-18",
  "extensions": ["com"],
  "total_records": 1050,
  "filtered_records": 742,
  "total_volume": 1250000.0,
  "average_price": 403.22,
  "sales": [
    {
      "domain": "libertypump.com",
      "price": 25000.0,
      "sale_type": "Private Seller",
      "venue": "Afternic",
      "extension": "com",
      "report_date": "2026-05-18",
      "source_url": "https://dropdax.com/blog/daily-domain-market-report-may-18-2026/",
      "marketplace": "dropdax"
    }
  ]
}
```

---

## Common Use Cases

### 1. “What sold for the most money this week?”

```bash
curl "http://localhost:7852/api/v1/sales/weekly-top?limit=10"
```

### 2. “All .ai sales above $10,000 this month”

```bash
curl "http://localhost:7852/api/v1/sales?period=month&extensions=ai&min_price=10000&limit=100"
```

### 3. “GoDaddy expired auctions this week”

```bash
curl "http://localhost:7852/api/v1/sales?period=week&venue=GoDaddy&limit=50"
```

### 4. “Compare two weeks (custom ranges)”

```bash
# Week 1
curl "http://localhost:7852/api/v1/sales/stats?period=custom&start_date=2026-05-01&end_date=2026-05-07"

# Week 2
curl "http://localhost:7852/api/v1/sales/stats?period=custom&start_date=2026-05-08&end_date=2026-05-14"
```

### 5. “Export top 100 .com sales to CSV” (PowerShell)

```powershell
$data = Invoke-RestMethod "http://localhost:7852/api/v1/sales?period=week&extensions=com&limit=100"
$data.sales | Export-Csv -Path "top-com-sales.csv" -NoTypeInformation
```

### 6. “Find which TLDs are active this week”

```bash
curl "http://localhost:7852/api/v1/sales/extensions?period=week"
```

---

## Using with n8n

[n8n](https://n8n.io/) can call this API with the **HTTP Request** node (GET, query parameters, JSON body parsing).

**Full guide (recommended):** **[docs/N8N.md](docs/N8N.md)** — prerequisites (n8n Cloud vs self-hosted), variables, query params, splitting the `sales` array, schedules, Sheets/Slack examples, timeouts, and errors.

**Starter workflow:** import **[docs/n8n-workflow-starter.json](docs/n8n-workflow-starter.json)** in n8n (**Workflows** → **Import from File**), then change the URL from `http://127.0.0.1:7852` to your VPS or public domain.

**Minimal checklist**

1. Use **GET** and URL `YOUR_BASE/api/v1/sales` (or `/api/v1/sales/weekly-top`, etc.).
2. Enable **Send Query Parameters** for `period`, `extensions`, `limit`, etc.
3. Set **Timeout** to **60000** ms (scraping can be slow the first time).
4. Use **Split Out Items** on field `sales` to get one n8n item per domain sale.

If n8n runs in Docker on the same VPS as this API, see **n8n and the API on the same VPS** in [DEPLOY.md](DEPLOY.md#6-n8n-and-the-api-on-the-same-vps).

---

## Deploy to GitHub & VPS

Repository: **https://github.com/Monjed1/domain-sales-api**

See **[DEPLOY.md](DEPLOY.md)** for full VPS setup. Quick deploy on server:

```bash
git clone https://github.com/Monjed1/domain-sales-api.git /opt/domain-sales-api
cd /opt/domain-sales-api
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

API on VPS: `http://YOUR_VPS_IP:7852/docs`

---

## Features

- Scrape DropDax daily market reports (top 150+ sales per day)
- Filter by TLD extension (`.com`, `.ai`, `.io`, etc.)
- Time periods: `day`, `week`, `month`, or custom date range
- Weekly top sales endpoint
- Aggregated stats by extension and venue
- Response caching (1 hour default)
- OpenAPI docs at `/docs`
- Docker-ready deployment on port **7852**

---

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `7852` | Server port |
| `DEBUG` | `false` | Debug mode |
| `CACHE_TTL_SECONDS` | `3600` | Cache lifetime (seconds) |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout when scraping |

---

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

---

## Notes

- DropDax publishes one report per trading day; `period=week` aggregates up to 7 daily reports.
- The main DropDax data engine (`dropdax.com/?date=...`) is Cloudflare-protected; this API uses publicly accessible blog reports.
- Respect DropDax terms of service and use reasonable request rates (built-in caching and concurrency limits).
- Additional marketplaces can be added by implementing new scrapers under `app/scrapers/`.

---

## License

MIT

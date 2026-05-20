# Using the Domain Sales API with n8n

This guide explains how to call the API from [n8n](https://n8n.io/) (cloud or self-hosted), parse JSON responses, and build common automations.

**Base URL examples**

- Local: `http://localhost:7852`
- VPS: `http://YOUR_VPS_IP:7852` or `https://api.yourdomain.com` (behind Nginx)

Paths are relative to that base (for example `/api/v1/sales`).

---

## 1. Prerequisites

| Scenario | What you need |
|----------|----------------|
| **n8n Cloud** | The API must be **publicly reachable** (HTTPS recommended). Use your VPS URL, domain, or a tunnel (ngrok, Cloudflare Tunnel) for development. |
| **Self-hosted n8n (Docker)** | Same host as API: often `http://host.docker.internal:7852` (Docker Desktop) or a **shared Docker network** + service hostname (see [DEPLOY.md](../DEPLOY.md#6-n8n-and-the-api-on-the-same-vps)). |
| **Self-hosted n8n (no Docker)** | `http://127.0.0.1:7852` if the API runs on the same machine. |

The API does **not** use API keys today. Store the base URL in n8n **Variables** or hardcode it in the HTTP Request node.

---

## 2. Store the base URL (recommended)

1. n8n **Settings** → **Variables** (or **Environments**, depending on your plan).
2. Add: `DOMAIN_SALES_API_BASE` = `https://api.yourdomain.com` (no trailing slash).

In **HTTP Request** → **URL**:

```text
={{ $vars.DOMAIN_SALES_API_BASE }}/api/v1/sales
```

If variables are unavailable, add a **Set** node first with `apiBase` and use `{{ $json.apiBase }}/api/v1/sales` in the next node.

---

## 3. HTTP Request node — setup

1. Add **HTTP Request**.
2. **Method:** `GET`
3. **URL:** for example `http://YOUR_VPS_IP:7852/api/v1/sales`
4. **Authentication:** `None`
5. Turn **Send Query Parameters** **ON** and add rows (section 4).
6. **Options** → **Timeout:** `60000` (first scrape can take 10–30 s).

**Response:** leave as JSON. The response body is available as `{{ $json }}` on the output item.

Optional header:

| Name | Value |
|------|--------|
| Accept | application/json |

---

## 4. Query parameters

In **HTTP Request** → **Send Query Parameters** → add parameters:

| Name | Example | Notes |
|------|---------|--------|
| period | week | day, week, month, custom |
| extensions | com,ai | comma-separated, no leading dot |
| limit | 50 | 1–10000 |
| sort_by | price | price, date, domain |
| sort_order | desc | asc or desc |
| min_price | 5000 | optional |
| venue | GoDaddy | optional partial match |
| start_date | 2026-05-01 | required if period=custom |
| end_date | 2026-05-18 | required if period=custom |

Equivalent one-line URL:

```text
http://YOUR_VPS_IP:7852/api/v1/sales?period=week&extensions=com&limit=20&sort_by=price&sort_order=desc
```

---

## 5. Reading the response

Top-level fields include `sales` (array), `filtered_records`, `total_volume`, `average_price`, `start_date`, `end_date`.

| Expression | Meaning |
|------------|---------|
| `{{ $json.sales }}` | All sale objects |
| `{{ $json.sales[0].domain }}` | First domain |

### One item per sale

- **Split Out Items** node → **Field To Split Out:** `sales`

Or **Code** node (JavaScript):

```javascript
const sales = $input.first().json.sales || [];
return sales.map((sale) => ({ json: sale }));
```

---

## 6. Example workflows

### A) Daily digest — top .com sales

1. **Schedule Trigger** (e.g. daily 08:00).
2. **HTTP Request** → `/api/v1/sales` with `period=day`, `extensions=com`, `limit=10`, `sort_by=price`, `sort_order=desc`.
3. **Split Out Items** on `sales`.
4. **Slack** / **Telegram** / **Email** — body example:  
   `{{ $json.domain }} — ${{ $json.price }} @ {{ $json.venue }}`

### B) Weekly top (all TLDs)

**HTTP Request** → GET `/api/v1/sales/weekly-top` with `limit=25`.

### C) Health then sales

1. GET `/api/v1/health`
2. **IF** → `{{ $json.status }}` equals `ok`
3. True branch: GET `/api/v1/sales` …

### D) Custom range → Google Sheets

1. GET `/api/v1/sales` with `period=custom`, `start_date`, `end_date`, `extensions=ai`.
2. Split `sales`.
3. **Google Sheets** → append columns: domain, price, venue, report_date.

### E) Full day report

GET `/api/v1/sales/daily/2026-05-18` (change date or use `{{ $json.reportDate }}` from a previous node).

---

## 7. n8n Cloud vs self-hosted

| n8n | API | URL |
|-----|-----|-----|
| Cloud | Public VPS / domain | `https://your-api-domain` |
| Cloud | Only localhost | Tunnel or make API public |
| Self-hosted Docker | API on host :7852 | `http://host.docker.internal:7852` (Desktop) |
| Self-hosted Docker | API in compose | Shared network + service name |

---

## 8. Timeouts and retries

Set **Timeout** to **60000** ms. Optionally enable **Retry On Fail** (e.g. 2 retries, 5 s wait).

---

## 9. Errors

Use **Continue On Fail** or an **Error Trigger** workflow. `404` on `/sales/daily/{date}` means no DropDax report for that date.

---

## 10. Import starter workflow

**Workflows** → **Import from File** → choose:

`docs/n8n-workflow-starter.json`

Edit the HTTP Request URL to your real base URL, then **Save** and **Execute**.

---

## 11. OpenAPI

Open `http://YOUR_HOST:7852/docs` or import **curl** from the README into HTTP Request (**Import from cURL**). Spec: `GET /openapi.json`.

---

## Endpoint quick reference

| Purpose | Path |
|---------|------|
| Filtered sales | `/api/v1/sales` |
| Weekly top | `/api/v1/sales/weekly-top` |
| Full day | `/api/v1/sales/daily/YYYY-MM-DD` |
| List reports | `/api/v1/sales/reports` |
| Stats | `/api/v1/sales/stats` |
| TLDs in period | `/api/v1/sales/extensions` |
| Health | `/api/v1/health` |

More detail: [README](../README.md).

# GitHub + VPS Deployment Guide

API runs on port **7852**.

## 1. Push to GitHub (from your PC)

### First time

```bash
cd "Domain search"
git init
git add .
git commit -m "Initial commit: Domain Sales Scraper API on port 7852"
```

Repository: **https://github.com/Monjed1/domain-sales-api**

If the remote is not set yet:

```bash
git branch -M main
git remote add origin https://github.com/Monjed1/domain-sales-api.git
git push -u origin main
```

Or with GitHub CLI:

```bash
gh auth login
gh repo create domain-sales-api --public --source=. --remote=origin --push
```

## 2. Prepare the VPS (Ubuntu 22.04+)

SSH into your server:

```bash
ssh root@YOUR_VPS_IP
```

Install Docker:

```bash
apt update && apt upgrade -y
apt install -y git curl ca-certificates
curl -fsSL https://get.docker.com | sh
systemctl enable docker
```

Open port **7852** in your firewall:

```bash
ufw allow OpenSSH
ufw allow 7852/tcp
ufw enable
```

(If you use a cloud panel, also allow TCP 7852 in the security group.)

## 3. Clone and run on VPS

```bash
mkdir -p /opt/domain-sales-api
cd /opt/domain-sales-api
git clone https://github.com/Monjed1/domain-sales-api.git .
cp .env.example .env
# optional: nano .env
docker compose -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
curl http://127.0.0.1:7852/api/v1/health
```

Public URLs:

- API root: `http://YOUR_VPS_IP:7852/`
- Docs: `http://YOUR_VPS_IP:7852/docs`

## 4. Update after code changes

On your PC, push to GitHub:

```bash
git add .
git commit -m "Your change description"
git push origin main
```

On the VPS (pull latest docs, n8n guide, and code — **run this after every GitHub update**):

```bash
cd /opt/domain-sales-api
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Or manually:

```bash
cd /opt/domain-sales-api
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

**After updating:** n8n workflows do not need changes unless the API URL or contract changed. If you only added documentation, rebuilding the container is optional but `git pull` keeps `docs/` on disk for your reference.

## 5. Optional: Nginx + domain + HTTPS

1. Point your domain A record to the VPS IP.
2. Copy `deploy/nginx-domain-sales-api.conf` to `/etc/nginx/sites-available/domain-sales-api`.
3. Replace `YOUR_DOMAIN`, enable the site, reload nginx.
4. Run `certbot --nginx -d YOUR_DOMAIN` for SSL.

The API stays on `127.0.0.1:7852`; Nginx proxies port 80/443 to it.

## 6. n8n and the API on the same VPS

If **n8n** and this API both run as Docker containers on one server:

1. **Simplest:** expose the API on the host (`7852:7852` as in `docker-compose.prod.yml`) and call it from n8n using `http://YOUR_VPS_PUBLIC_IP:7852` or your Nginx HTTPS URL. No extra Docker network needed.

2. **Same Docker Compose network:** add both services under one `docker-compose.yml` with a shared `networks:` entry. From the n8n container, use `http://domain-sales-api:7852` (use the **service name** from compose as hostname).

3. **n8n on host, API in Docker:** use `http://127.0.0.1:7852` from n8n on the host. If n8n is inside Docker and the API is published to the host, use `http://host.docker.internal:7852` (Docker Desktop) or the host gateway IP on Linux.

**n8n Cloud** cannot reach `127.0.0.1` on your laptop for production; use a public URL (VPS + firewall + optional Nginx + HTTPS).

Workflow examples: [docs/N8N.md](docs/N8N.md).

## 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| Port in use | `ss -tlnp \| grep 7852` |
| Container down | `docker compose -f docker-compose.prod.yml logs -f` |
| Rebuild clean | `docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d --build` |

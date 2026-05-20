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

Repository: **https://github.com/monjed1/domain-sales-api**

If the remote is not set yet:

```bash
git branch -M main
git remote add origin https://github.com/monjed1/domain-sales-api.git
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
git clone https://github.com/monjed1/domain-sales-api.git .
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
git push
```

On the VPS:

```bash
cd /opt/domain-sales-api
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Or manually:

```bash
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Optional: Nginx + domain + HTTPS

1. Point your domain A record to the VPS IP.
2. Copy `deploy/nginx-domain-sales-api.conf` to `/etc/nginx/sites-available/domain-sales-api`.
3. Replace `YOUR_DOMAIN`, enable the site, reload nginx.
4. Run `certbot --nginx -d YOUR_DOMAIN` for SSL.

The API stays on `127.0.0.1:7852`; Nginx proxies port 80/443 to it.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port in use | `ss -tlnp \| grep 7852` |
| Container down | `docker compose -f docker-compose.prod.yml logs -f` |
| Rebuild clean | `docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d --build` |

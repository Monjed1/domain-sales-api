#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/domain-sales-api}"
COMPOSE_FILE="docker-compose.prod.yml"

cd "$APP_DIR"

echo "==> Pulling latest code..."
git pull origin main

echo "==> Building and starting API on port 7852..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "==> Health check..."
sleep 5
curl -fsS "http://127.0.0.1:7852/api/v1/health" && echo ""

echo "==> Done. API: http://$(hostname -I | awk '{print $1}'):7852/docs"

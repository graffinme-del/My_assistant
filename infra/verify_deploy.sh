#!/usr/bin/env sh
# Быстрая проверка после деплоя: API и веб отвечают на фиксированных портах.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "verify: docker compose ps"
docker compose --env-file .env ps

echo "verify: GET :8000/health"
curl -fsS --max-time 15 "http://127.0.0.1:8000/health" | head -c 200
echo ""

echo "verify: GET :8080/ (nginx)"
curl -fsS --max-time 15 -o /dev/null -w "HTTP %{http_code}\n" "http://127.0.0.1:8080/"

echo "verify: OK"

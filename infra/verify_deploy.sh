#!/usr/bin/env sh
# Проверка после деплоя (тот же compose-файл, что и в GitHub Actions).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "verify: docker compose ps"
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env ps

echo "verify: wait for API"
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS --max-time 2 "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "verify: GET :8000/health"
curl -fsS --max-time 15 "http://127.0.0.1:8000/health" | head -c 200
echo ""

echo "verify: GET :8080/ (nginx)"
curl -fsS --max-time 15 -o /dev/null -w "HTTP %{http_code}\n" "http://127.0.0.1:8080/"

echo "verify: OK"

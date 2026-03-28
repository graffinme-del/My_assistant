#!/usr/bin/env sh
# Проверка после деплоя. COMPOSE: runtime.compose.yml (GHCR) или infra/compose.prod.yml (локальный build).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="${MY_ASSISTANT_COMPOSE:-runtime.compose.yml}"
if [ ! -f "$COMPOSE" ]; then
  COMPOSE="infra/compose.prod.yml"
fi

dc() {
  if [ -f .env.local ]; then
    if echo "$COMPOSE" | grep -q '^infra/'; then
      docker compose --project-directory . -f "$COMPOSE" --env-file .env --env-file .env.local "$@"
    else
      docker compose -f "$COMPOSE" --env-file .env --env-file .env.local "$@"
    fi
  else
    if echo "$COMPOSE" | grep -q '^infra/'; then
      docker compose --project-directory . -f "$COMPOSE" --env-file .env "$@"
    else
      docker compose -f "$COMPOSE" --env-file .env "$@"
    fi
  fi
}

echo "verify: using compose file $COMPOSE"
echo "verify: docker compose ps"
dc ps

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

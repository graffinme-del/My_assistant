#!/usr/bin/env sh
# Гарантирует наличие .env и убирает «пустые» строки VAR= для портов —
# иначе docker compose подставляет пустую строку и ломает публикацию портов.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "ensure_env: создаю .env из .env.example (добавьте секреты в .env на сервере)."
  cp -f .env.example .env
fi

# Удаляем строки, где значение пустое (VAR= или VAR=   ) — только для переменных портов.
awk '
  /^APP_PORT=[[:space:]]*$/ { next }
  /^WEB_PORT=[[:space:]]*$/ { next }
  /^POSTGRES_PORT=[[:space:]]*$/ { next }
  /^REDIS_PORT=[[:space:]]*$/ { next }
  /^MINIO_API_PORT=[[:space:]]*$/ { next }
  /^MINIO_CONSOLE_PORT=[[:space:]]*$/ { next }
  { print }
' .env > .env.tmp && mv .env.tmp .env

echo "ensure_env: OK (.env готов)"

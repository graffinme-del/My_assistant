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

# Удаляем строки VAR= без значения для портов (sed -e — без скобок | в grep и без многострочного awk).
sed -e '/^APP_PORT=[[:space:]]*$/d' -e '/^WEB_PORT=[[:space:]]*$/d' -e '/^POSTGRES_PORT=[[:space:]]*$/d' -e '/^REDIS_PORT=[[:space:]]*$/d' -e '/^MINIO_API_PORT=[[:space:]]*$/d' -e '/^MINIO_CONSOLE_PORT=[[:space:]]*$/d' .env > .env.tmp && mv .env.tmp .env

echo "ensure_env: OK (.env готов)"

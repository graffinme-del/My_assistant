#!/usr/bin/env sh
# .env создаётся из .env.example только если файла ещё нет.
# Новые KEY из .env.example дописываются в .env только если такого ключа ещё нет — ваши значения не затираются.
# Секреты держите в .env.local (не коммитится, деплой его не скачивает); docker compose читает .env и .env.local.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "ensure_env: создаю .env из .env.example (секреты — в .env.local, см. .env.example и .env.local.example)."
  cp -f .env.example .env
fi

# Дописать отсутствующие ключи из шаблона, не меняя существующие строки.
if [ -f .env.example ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    case "$line" in
      *=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    if ! grep -q "^${key}=" .env 2>/dev/null; then
      echo "$line" >> .env
    fi
  done < .env.example
fi

# Пустые VAR= для портов ломают docker compose — удаляем только их.
sed -e '/^APP_PORT=[[:space:]]*$/d' -e '/^WEB_PORT=[[:space:]]*$/d' -e '/^POSTGRES_PORT=[[:space:]]*$/d' -e '/^REDIS_PORT=[[:space:]]*$/d' -e '/^MINIO_API_PORT=[[:space:]]*$/d' -e '/^MINIO_CONSOLE_PORT=[[:space:]]*$/d' .env > .env.tmp && mv .env.tmp .env

echo "ensure_env: OK"

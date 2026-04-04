#!/usr/bin/env sh
# Только первый запуск: если .env нет — копируем из env.example (шаблон в репозитории).
# НИЧЕГО не дописываем из шаблона при каждом деплое — иначе могли появляться
# дубликаты вроде второй строки OPENAI_API_KEY= (пустой), и контейнер видел пустой ключ.
# Пустые строки VAR= только для портов — удаляем (docker compose ломается).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  if [ -f env.example ]; then
    echo "ensure_env: создаю .env из env.example (один раз). Секреты можно держать в .env.local."
    cp -f env.example .env
  elif [ -f .env.example ]; then
    echo "ensure_env: создаю .env из .env.example (устаревшее имя; используйте env.example)."
    cp -f .env.example .env
  else
    echo "ensure_env: не найден env.example — положите шаблон из репозитория."
    exit 1
  fi
fi

sed -e '/^APP_PORT=[[:space:]]*$/d' -e '/^WEB_PORT=[[:space:]]*$/d' -e '/^POSTGRES_PORT=[[:space:]]*$/d' -e '/^REDIS_PORT=[[:space:]]*$/d' -e '/^MINIO_API_PORT=[[:space:]]*$/d' -e '/^MINIO_CONSOLE_PORT=[[:space:]]*$/d' .env > .env.tmp && mv .env.tmp .env

echo "ensure_env: OK (.env не перезаписывается шаблоном; новые ключи смотри в env.example и добавь вручную при необходимости)"

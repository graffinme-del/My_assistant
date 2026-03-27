#!/usr/bin/env sh
# Создаёт .env из шаблона, если файла нет (иначе docker compose ломает порты и API).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -f .env ]; then
  echo "ensure_env: создаю .env из .env.example (добавьте ключи в .env на сервере)."
  cp -f .env.example .env
fi

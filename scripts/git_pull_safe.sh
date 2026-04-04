#!/usr/bin/env bash
# Безопасный git pull: не даём устаревшему отслеживаемому .env.example блокировать merge.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .git ]; then
  echo "Не git-репозиторий: $ROOT" >&2
  exit 1
fi

# Старые клоны: сброс локальных правок в отслеживаемом .env.example (в новых версиях файла в репо нет)
git checkout -- .env.example 2>/dev/null || true

BRANCH="${1:-main}"
git pull origin "$BRANCH"
echo "OK: pulled origin/$BRANCH. Шаблон переменных в репозитории: env.example"

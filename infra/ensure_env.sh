#!/usr/bin/env sh
# Только первый запуск: если .env нет — копируем из env.example (шаблон в репозитории).
# НИЧЕГО не дописываем из шаблона при каждом деплое — иначе могли появляться
# дубликаты вроде второй строки OPENAI_API_KEY= (пустой), и контейнер видел пустой ключ.
# Пустые строки VAR= только для портов — удаляем (docker compose ломается).
# При создании .env подменяем публичные owner-dev-token/member-dev-token на случайные.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

_rand_token() {
  # url-safe ~32 bytes; fallbacks for minimal images
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -d '\n/+=' | head -c 40
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
    return
  fi
  # last resort: mixed pid/time (still better than a public default)
  echo "tok-$(date +%s)-$$-$(awk 'BEGIN{srand(); print int(rand()*1e9)}')"
}

_rewrite_dev_tokens() {
  # Replace well-known public defaults in the given env file.
  f="$1"
  owner="$(_rand_token)"
  member="$(_rand_token)"
  # Keep owner and member distinct if RNG ever collides.
  while [ "$member" = "$owner" ]; do
    member="$(_rand_token)"
  done
  tmp="${f}.tokens.tmp"
  # portable-ish: rewrite only exact default assignments
  awk -v o="$owner" -v m="$member" '
    BEGIN { changed=0 }
    /^OWNER_TOKEN=owner-dev-token[[:space:]]*$/ { print "OWNER_TOKEN=" o; changed=1; next }
    /^MEMBER_TOKEN=member-dev-token[[:space:]]*$/ { print "MEMBER_TOKEN=" m; changed=1; next }
    { print }
    END { if (changed) exit 0; exit 0 }
  ' "$f" > "$tmp"
  mv "$tmp" "$f"
  if grep -q '^OWNER_TOKEN=owner-dev-token[[:space:]]*$' "$f" 2>/dev/null; then
    :
  else
    echo "ensure_env: OWNER_TOKEN/MEMBER_TOKEN set to random values (not the public owner-dev-token defaults)."
    echo "ensure_env: скопируйте OWNER_TOKEN в localStorage.apiToken веб-клиента (Application → Local Storage)."
  fi
}

CREATED=0
if [ ! -f .env ]; then
  if [ -f env.example ]; then
    echo "ensure_env: создаю .env из env.example (один раз). Секреты можно держать в .env.local."
    cp -f env.example .env
    CREATED=1
  elif [ -f .env.example ]; then
    echo "ensure_env: создаю .env из .env.example (устаревшее имя; используйте env.example)."
    cp -f .env.example .env
    CREATED=1
  else
    echo "ensure_env: не найден env.example — положите шаблон из репозитория."
    exit 1
  fi
fi

if [ "$CREATED" -eq 1 ]; then
  _rewrite_dev_tokens .env
elif grep -qE '^OWNER_TOKEN=owner-dev-token[[:space:]]*$|^MEMBER_TOKEN=member-dev-token[[:space:]]*$' .env 2>/dev/null; then
  echo "ensure_env: WARNING — в .env всё ещё публичные owner-dev-token/member-dev-token."
  echo "ensure_env: при APP_ENV=production API откажется стартовать. Смените токены или пересоздайте .env."
fi

sed -e '/^APP_PORT=[[:space:]]*$/d' -e '/^WEB_PORT=[[:space:]]*$/d' -e '/^POSTGRES_PORT=[[:space:]]*$/d' -e '/^REDIS_PORT=[[:space:]]*$/d' -e '/^MINIO_API_PORT=[[:space:]]*$/d' -e '/^MINIO_CONSOLE_PORT=[[:space:]]*$/d' .env > .env.tmp && mv .env.tmp .env

echo "ensure_env: OK (.env не перезаписывается шаблоном; новые ключи смотри в env.example и добавь вручную при необходимости)"

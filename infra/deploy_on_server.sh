#!/usr/bin/env bash
# Единая точка деплоя: сервер = git-рабочая копия main (как у тебя на ПК).
# Первый запуск: старый каталог без .git переименовывается в *.pre-git.*, .env сохраняется.
# Дальше: git fetch + reset --hard origin/main → ensure_env → docker compose.
set -euo pipefail

ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
REPO="${GIT_REPO_URL:-https://github.com/graffinme-del/My_assistant.git}"
BRANCH="${GIT_BRANCH:-main}"

log() { echo "[deploy_on_server] $*"; }

stop_stack_in_dir() {
  local d="$1"
  [ -d "$d" ] || return 0
  if [ -f "$d/infra/compose.prod.yml" ] && [ -f "$d/.env" ]; then
    (cd "$d" && docker compose --project-directory . -f infra/compose.prod.yml --env-file .env down --remove-orphans 2>/dev/null) || true
  fi
  (cd "$d" 2>/dev/null && docker compose down --remove-orphans 2>/dev/null) || true
  docker ps -q --filter name=my_assistant | xargs -r docker stop 2>/dev/null || true
}

assert_compose_sane() {
  local d="$1"
  grep -q '8000:8000' "$d/docker-compose.yml"
  grep -q '8080:80' "$d/docker-compose.yml"
  ! grep -q 'APP_PORT}:8000' "$d/docker-compose.yml"
  ! grep -q 'WEB_PORT}:80' "$d/docker-compose.yml"
  grep -q '8000:8000' "$d/infra/compose.prod.yml"
  grep -q '8080:80' "$d/infra/compose.prod.yml"
}

if [ ! -d "$ROOT/.git" ]; then
  log "нет .git в $ROOT — миграция на git-deploy"
  stop_stack_in_dir "$ROOT"
  BAK=""
  if [ -d "$ROOT" ]; then
    BAK="${ROOT}.pre-git.$(date +%s)"
    mv "$ROOT" "$BAK"
    log "старый каталог сохранён: $BAK"
  fi
  mkdir -p "$(dirname "$ROOT")"
  # Полный clone (без --depth): иначе shallow fetch на сервере часто ломает reset на следующий push.
  git clone --branch "$BRANCH" "$REPO" "$ROOT"
  if [ -n "$BAK" ]; then
    for f in .env .env.backup; do
      if [ -f "$BAK/$f" ]; then
        cp -a "$BAK/$f" "$ROOT/"
        log "восстановлен $f из бэкапа"
      fi
    done
  fi
else
  log "обновление из git: $ROOT"
  stop_stack_in_dir "$ROOT"
  cd "$ROOT"
  git remote set-url origin "$REPO"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git reset --hard "origin/$BRANCH"
fi

cd "$ROOT"
assert_compose_sane "$ROOT"
chmod +x infra/ensure_env.sh infra/verify_deploy.sh 2>/dev/null || true

test -f .env || cp -f .env.example .env
sh infra/ensure_env.sh

docker compose --project-directory . -f infra/compose.prod.yml --env-file .env pull || true
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env up -d --build

sh infra/verify_deploy.sh
log "OK $(git rev-parse --short HEAD)"

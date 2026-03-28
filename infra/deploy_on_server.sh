#!/usr/bin/env bash
# Единая точка деплоя: рабочая копия = origin/main. Не кладите сюда второй rsync/копирование с ПК — сломаете дерево.
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
  # stop не удаляет контейнер — без rm следующий up даёт «name already in use».
  docker ps -aq --filter name=my_assistant | xargs -r docker rm -f 2>/dev/null || true
  docker network rm my_assistant_default 2>/dev/null || true
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

require_infra() {
  local d="$1"
  local f
  for f in infra/compose.prod.yml infra/ensure_env.sh infra/verify_deploy.sh infra/deploy_on_server.sh; do
    if [ ! -f "$d/$f" ]; then
      log "FATAL: нет $f после синхронизации с origin/$BRANCH — дерево битое или не тот remote"
      exit 1
    fi
  done
}

mkdir -p "$ROOT"

if [ ! -d "$ROOT/.git" ]; then
  log "первичная привязка: git init в $ROOT"
  stop_stack_in_dir "$ROOT"
  cd "$ROOT"
  git init
  git remote remove origin 2>/dev/null || true
  git remote add origin "$REPO"
  git fetch origin "$BRANCH"
  git checkout -f -B "$BRANCH" "origin/$BRANCH"
else
  log "git fetch + reset --hard (сначала чиним файлы на диске)"
  cd "$ROOT"
  git remote set-url origin "$REPO"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  stop_stack_in_dir "$ROOT"
fi

cd "$ROOT"
git config core.fileMode false
require_infra "$ROOT"
assert_compose_sane "$ROOT"

chmod +x infra/ensure_env.sh infra/verify_deploy.sh 2>/dev/null || true

test -f .env || cp -f .env.example .env
sh infra/ensure_env.sh

docker compose --project-directory . -f infra/compose.prod.yml --env-file .env pull || true
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env up -d --build

sh infra/verify_deploy.sh
log "OK $(git rev-parse --short HEAD)"

#!/usr/bin/env bash
# Прод: без git и без docker build на сервере. Каждый запуск тянет с GitHub raw актуальный
# runtime.compose.yml + скрипты; контейнеры из ghcr.io (собираются в GitHub Actions).
# Копирование старого проекта с ПК на /opt больше не может подменить образы — только .env трогайте вручную.
set -euo pipefail

ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
BRANCH="${GIT_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/graffinme-del/My_assistant/${BRANCH}"

log() { echo "[deploy_on_server] $*"; }

mkdir -p "$ROOT/infra"
cd "$ROOT"

# .env.local не скачивается с GitHub — только ваши секреты; при наличии подмешивается поверх .env.
COMPOSE_ENV=(--env-file .env)
[ -f .env.local ] && COMPOSE_ENV+=(--env-file .env.local)

stop_all() {
  local f
  for f in runtime.compose.yml infra/compose.prod.yml docker-compose.yml; do
    if [ -f "$ROOT/$f" ] && [ -f "$ROOT/.env" ]; then
      (cd "$ROOT" && docker compose -f "$f" "${COMPOSE_ENV[@]}" down --remove-orphans 2>/dev/null) || true
    fi
  done
  (cd "$ROOT" 2>/dev/null && docker compose "${COMPOSE_ENV[@]}" down --remove-orphans 2>/dev/null) || true
  docker ps -aq --filter "label=com.docker.compose.project=my_assistant" | xargs -r docker rm -f 2>/dev/null || true
  docker ps -aq --filter name=my_assistant | xargs -r docker rm -f 2>/dev/null || true
  docker network rm my_assistant_default 2>/dev/null || true
}

stop_all

log "curl: runtime.compose.yml, ensure_env, verify_deploy, .env.example"
curl -fsSL -o runtime.compose.yml "${RAW}/runtime.compose.yml"
curl -fsSL -o infra/ensure_env.sh "${RAW}/infra/ensure_env.sh"
curl -fsSL -o infra/verify_deploy.sh "${RAW}/infra/verify_deploy.sh"
chmod +x infra/ensure_env.sh infra/verify_deploy.sh

curl -fsSL -o .env.example "${RAW}/.env.example"
curl -fsSL -o .env.local.example "${RAW}/.env.local.example" || log "нет .env.local.example в ветке — пропуск"
# Резервная копия перед ensure_env (на случай ручного отката: cp .env.bak .env)
if [ -f .env ]; then
  cp -a .env .env.bak
  log "сохранена копия .env → .env.bak"
fi
test -f .env || cp -f .env.example .env
sh infra/ensure_env.sh

export MY_ASSISTANT_COMPOSE=runtime.compose.yml

grep -q 'ghcr.io/graffinme-del/my_assistant' runtime.compose.yml
grep -q '8000:8000' runtime.compose.yml
grep -q '8080:80' runtime.compose.yml

log "docker compose pull + up (ghcr.io)"
docker compose -f runtime.compose.yml "${COMPOSE_ENV[@]}" pull
docker compose -f runtime.compose.yml "${COMPOSE_ENV[@]}" up -d

sh infra/verify_deploy.sh
log "OK — сервер на образах GHCR, исходники на диске не нужны"

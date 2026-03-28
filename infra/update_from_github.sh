#!/usr/bin/env sh
# Обновить /opt/my_assistant с GitHub без git (каталог деплоя — rsync, .git там нет).
# Скрипты infra подтягиваются с raw.githubusercontent.com, чтобы не портить их tr/sed.
set -eu
REPO="${MY_ASSISTANT_REPO:-graffinme-del/My_assistant}"
BRANCH="${MY_ASSISTANT_BRANCH:-main}"
ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
TMP="${TMPDIR:-/tmp}/ma-src-$$"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

mkdir -p "$TMP"
curl -fsSL -o "$TMP/src.tar.gz" "https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
tar -xzf "$TMP/src.tar.gz" -C "$TMP"
SRC=$(find "$TMP" -maxdepth 1 -type d -name "My_assistant-*" | head -1)
test -n "$SRC"

rsync -a --delete \
  --exclude ".env" \
  --exclude ".env.backup" \
  --exclude ".env.*.local" \
  "$SRC/" "$ROOT/"

curl -fsSL -o "$ROOT/infra/ensure_env.sh" "https://raw.githubusercontent.com/${REPO}/${BRANCH}/infra/ensure_env.sh"
curl -fsSL -o "$ROOT/infra/verify_deploy.sh" "https://raw.githubusercontent.com/${REPO}/${BRANCH}/infra/verify_deploy.sh"
chmod +x "$ROOT/infra/ensure_env.sh" "$ROOT/infra/verify_deploy.sh"

cd "$ROOT"
test -f .env || cp -f .env.example .env
sh infra/ensure_env.sh
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env pull || true
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env up -d --build
sh infra/verify_deploy.sh
echo "update_from_github: OK"

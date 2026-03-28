#!/usr/bin/env bash
set -euo pipefail
cd /opt/my_assistant
REPO="${MY_ASSISTANT_REPO:-graffinme-del/My_assistant}"
BRANCH="${MY_ASSISTANT_BRANCH:-main}"
mkdir -p infra
curl -fsSL -o infra/ensure_env.sh "https://raw.githubusercontent.com/${REPO}/${BRANCH}/infra/ensure_env.sh"
curl -fsSL -o infra/verify_deploy.sh "https://raw.githubusercontent.com/${REPO}/${BRANCH}/infra/verify_deploy.sh"
chmod +x infra/*.sh
ids=$(docker ps -q --filter name=my_assistant 2>/dev/null || true)
if [ -n "${ids:-}" ]; then
  docker stop $ids || true
fi
[ -f .env ] || cp -f .env.example .env
sh infra/ensure_env.sh
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env pull || true
docker compose --project-directory . -f infra/compose.prod.yml --env-file .env up -d --build
sh infra/verify_deploy.sh
ss -tlnp 2>/dev/null | grep -E ':8080|:8000' || true

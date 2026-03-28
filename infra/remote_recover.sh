#!/usr/bin/env bash
set -euo pipefail
cd /opt/my_assistant
for f in infra/ensure_env.sh infra/verify_deploy.sh; do
  if [ -f "$f" ]; then
    tr -d '\r' <"$f" >"$f.tmp" && mv "$f.tmp" "$f"
  fi
done
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

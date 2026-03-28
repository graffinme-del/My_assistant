#!/usr/bin/env bash
# Аварийное восстановление = полный деплой из git (см. deploy_on_server.sh).
export GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/graffinme-del/My_assistant.git}"
export GIT_BRANCH="${GIT_BRANCH:-main}"
export DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
exec bash "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/deploy_on_server.sh"

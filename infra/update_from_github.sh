#!/usr/bin/env sh
# Обёртка: то же, что делает GitHub Actions (git + compose), без rsync.
export GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/graffinme-del/My_assistant.git}"
export GIT_BRANCH="${GIT_BRANCH:-main}"
export DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
exec bash "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/deploy_on_server.sh"

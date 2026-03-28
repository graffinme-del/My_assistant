#!/usr/bin/env sh
export DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/my_assistant}"
export GIT_BRANCH="${GIT_BRANCH:-main}"
curl -fsSL "https://raw.githubusercontent.com/graffinme-del/My_assistant/${GIT_BRANCH}/infra/deploy_on_server.sh" | bash

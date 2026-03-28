#!/bin/sh
curl -sS -H 'Content-Type: application/json' -H 'X-API-Token: owner-dev-token' \
  -d '{"text":"hello"}' \
  "http://127.0.0.1:8000/assistant/ingest-text"

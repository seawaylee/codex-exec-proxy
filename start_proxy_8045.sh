#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  echo "missing virtualenv at $ROOT_DIR/.venv, run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

: "${OPENAI_BASE_URL:?OPENAI_BASE_URL is required, e.g. https://gmn.chuangzuoli.com}"
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

export CODEX_WORKDIR="${CODEX_WORKDIR:-/tmp}"
export CODEX_SANDBOX_MODE="${CODEX_SANDBOX_MODE:-read-only}"
export CODEX_LOCAL_ONLY="${CODEX_LOCAL_ONLY:-false}"

# Auth is disabled by default.
# Set ENABLE_PROXY_AUTH=true and PROXY_API_KEY=<token> to enforce bearer auth.
if [ "${ENABLE_PROXY_AUTH:-false}" = "true" ]; then
  : "${PROXY_API_KEY:?PROXY_API_KEY is required when ENABLE_PROXY_AUTH=true}"
else
  unset PROXY_API_KEY
fi

exec "$ROOT_DIR/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8045

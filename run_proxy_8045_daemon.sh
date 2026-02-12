#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILE="${CODEX_PROXY_ENV_FILE:-}"
if [ -z "$ENV_FILE" ]; then
  if [ -f "$ROOT_DIR/.proxy.local.env" ]; then
    ENV_FILE="$ROOT_DIR/.proxy.local.env"
  elif [ -n "${HOME:-}" ] && [ -f "${HOME}/.codex-reverse-proxy.env" ]; then
    ENV_FILE="${HOME}/.codex-reverse-proxy.env"
  fi
fi

if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

: "${OPENAI_BASE_URL:?OPENAI_BASE_URL is required (set in environment or env file)}"
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required (set in environment or env file)}"
export OPENAI_BASE_URL OPENAI_API_KEY

export PATH="/Users/NikoBelic/.volta/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export CODEX_PATH="${CODEX_PATH:-/Users/NikoBelic/.volta/bin/codex}"
export CODEX_TIMEOUT="${CODEX_TIMEOUT:-120}"

# Keep auth disabled by default.
unset ENABLE_PROXY_AUTH
unset PROXY_API_KEY

exec "$ROOT_DIR/start_proxy_8045.sh"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRIM_SCRIPT="$ROOT_DIR/scripts/trim_log.sh"

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
export CODEX_TIMEOUT="${CODEX_TIMEOUT:-300}"

# Keep auth disabled by default.
unset ENABLE_PROXY_AUTH
unset PROXY_API_KEY

LOG_STDOUT_PATH="${LOG_STDOUT_PATH:-$ROOT_DIR/logs/stdout.log}"
LOG_STDERR_PATH="${LOG_STDERR_PATH:-$ROOT_DIR/logs/stderr.log}"
LOG_MAX_BYTES="${LOG_MAX_BYTES:-52428800}"  # 50 MiB
LOG_KEEP_BYTES="${LOG_KEEP_BYTES:-10485760}"  # keep last 10 MiB
LOG_TRIM_INTERVAL_SECONDS="${LOG_TRIM_INTERVAL_SECONDS:-300}"  # every 5 minutes

mkdir -p "$(dirname "$LOG_STDOUT_PATH")" "$(dirname "$LOG_STDERR_PATH")"
touch "$LOG_STDOUT_PATH" "$LOG_STDERR_PATH"

trim_logs_once() {
  if [ -x "$TRIM_SCRIPT" ]; then
    "$TRIM_SCRIPT" "$LOG_STDOUT_PATH" "$LOG_MAX_BYTES" "$LOG_KEEP_BYTES" || true
    "$TRIM_SCRIPT" "$LOG_STDERR_PATH" "$LOG_MAX_BYTES" "$LOG_KEEP_BYTES" || true
  fi
}

start_log_trimmer() {
  (
    while true; do
      trim_logs_once
      sleep "$LOG_TRIM_INTERVAL_SECONDS"
    done
  ) >/dev/null 2>&1 &
  TRIMMER_PID="$!"
}

trim_logs_once
TRIMMER_PID=""
start_log_trimmer

cleanup() {
  if [ -n "${TRIMMER_PID:-}" ]; then
    kill "$TRIMMER_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

if [ "${CODEX_DAEMON_TEST_MODE:-false}" = "true" ]; then
  exit 0
fi

"$ROOT_DIR/start_proxy_8045.sh"

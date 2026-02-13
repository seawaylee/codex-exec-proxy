#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="${1:-}"
MAX_BYTES="${2:-}"
KEEP_BYTES="${3:-}"

if [ -z "$LOG_FILE" ] || [ -z "$MAX_BYTES" ] || [ -z "$KEEP_BYTES" ]; then
  echo "usage: $0 <log_file> <max_bytes> <keep_bytes>" >&2
  exit 2
fi

if [ ! -f "$LOG_FILE" ]; then
  exit 0
fi

if [ "$MAX_BYTES" -le 0 ] || [ "$KEEP_BYTES" -le 0 ]; then
  exit 0
fi

if [ "$KEEP_BYTES" -gt "$MAX_BYTES" ]; then
  KEEP_BYTES="$MAX_BYTES"
fi

current_bytes="$(wc -c < "$LOG_FILE" | tr -d '[:space:]')"
if [ -z "$current_bytes" ] || [ "$current_bytes" -le "$MAX_BYTES" ]; then
  exit 0
fi

tmp_file="$(mktemp "${LOG_FILE}.trim.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT

# Keep only the newest bytes to keep recent logs.
tail -c "$KEEP_BYTES" "$LOG_FILE" > "$tmp_file"
mv "$tmp_file" "$LOG_FILE"


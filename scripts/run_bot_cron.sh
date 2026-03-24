#!/usr/bin/env bash
# Started by cron on weekdays; flock prevents duplicate long-running bot processes.
set -euo pipefail
ROOT="/home/marckoby/dev/trading_bot.1001"
LOG="$ROOT/logs/cron.log"
mkdir -p "$ROOT/logs"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "$(date -Is) error: missing venv at $PY" >>"$LOG"
  exit 1
fi
if flock -n /tmp/trading_bot.1001.lock "$PY" "$ROOT/bot.py" >>"$LOG" 2>&1; then
  :
else
  echo "$(date -Is) skipped — bot already running (lock held)" >>"$LOG"
fi

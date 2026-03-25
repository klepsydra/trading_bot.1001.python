#!/usr/bin/env bash
# Weekday cron: one trading tick. Schedule every minute during the session for ~60s Python-loop parity.
set -euo pipefail
ROOT="/home/marckoby/dev/trading_bot.1001"
LOG="$ROOT/log/cron.log"
mkdir -p "$ROOT/log" "$ROOT/tmp/trading"
cd "$ROOT"
set -a
# shellcheck disable=SC1090
[ -f "$ROOT/.env" ] && . "$ROOT/.env"
set +a
if ! command -v bundle >/dev/null 2>&1; then
  echo "$(date -Is) error: bundle not in PATH" >>"$LOG"
  exit 1
fi
if flock -n /tmp/trading_bot.1001.lock env RAILS_ENV=production bundle exec bin/rails runner "TradingIterationJob.perform_now" >>"$LOG" 2>&1; then
  :
else
  echo "$(date -Is) skipped — tick already running (lock held)" >>"$LOG"
fi

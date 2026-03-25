# trading_bot.1001

Rails 8 app: **momentum / leveraged-ETF** strategy on **Alpaca** (paper by default), ported from the legacy Python bot.

## Stack

- Ruby on Rails 8, SQLite (swap `config/database.yml` for PostgreSQL in production if you prefer)
- Alpaca **Trading** + **Market Data** HTTP APIs via Faraday (`app/services/trading/broker.rb`)
- One **tick** = `TradingIterationJob` → `Trading::Runner` (same logic as the old `bot.py` loop body)

## Setup

```bash
cd /home/marckoby/dev/trading_bot.1001
bundle install
cp .env.example .env   # add Alpaca keys
bin/rails db:prepare
```

## Run a single tick (manual)

```bash
bin/rails trading:tick
# or
bin/rails runner "TradingIterationJob.perform_now"
```

## Web process (health check)

```bash
bin/rails server
```

Open `/` or `/up` (Rails health).

## Cron (production-style)

`scripts/run_bot_cron.sh` loads `.env`, uses `flock`, and runs **one** tick under `RAILS_ENV=production`. Schedule **every minute** during the session if you want parity with the old 60-second loop, e.g. with `CRON_TZ=America/New_York`:

```cron
* 9-15 * * 1-5 /home/marckoby/dev/trading_bot.1001/scripts/run_bot_cron.sh
```

Refine hours to match your risk window (`config/trading.yml`).

## Config

- **Trading parameters**: `config/trading.yml` (ticker pairs, thresholds, risk).
- **Never commit** real API keys; use `.env` (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`).

## Optional: Solid Queue later

This tree uses **cron + `perform_now`** so you do not need a job worker process. To move to Solid Queue + recurring YAML, add `solid_queue`, run its installer, and replace the cron tick with a recurring job.

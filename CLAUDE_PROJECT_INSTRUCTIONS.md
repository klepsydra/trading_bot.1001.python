# CLAUDE PROJECT INSTRUCTIONS — Momentum Trading Bot (`trading_bot.1001`)

## Stack

- **Ruby on Rails 8** — primary codebase.
- **Alpaca** paper trading (HTTP APIs via `Trading::Broker` + Faraday).
- **One tick** = `TradingIterationJob` → `Trading::Runner#tick` (equivalent to one pass of the former Python `loop_iteration`).

## Project layout

```
config/trading.yml              ← tune pairs, signal weights, risk, session window
app/services/trading/broker.rb  ← Alpaca trading + market data HTTP client
app/services/trading/signals.rb ← z-score, RSI, EMA, volume composite (ported)
app/services/trading/risk_manager.rb
app/services/trading/trade_logger.rb   ← CSV append log/trades.csv
app/services/trading/daily_drawdown_store.rb  ← tmp/trading/day_start_portfolio.json
app/services/trading/runner.rb  ← orchestrates one tick
app/jobs/trading_iteration_job.rb
scripts/run_bot_cron.sh         ← cron: flock + bundle exec rails runner
```

## Ticker pairs

| Base (signal) | Leveraged ETF | Leverage |
|---------------|---------------|----------|
| QQQ           | TQQQ          | 3×       |
| SPY           | SPYU          | 4×       |
| IWM           | TNA           | 3×       |
| DIA           | UDOW          | 3×       |

## Signal engine

Same composite as the Python version (weights and thresholds in `config/trading.yml`).

## Risk

- Daily drawdown halt, max allocation per name, fractional-Kelly-style sizing, bracket SL/TP on entry (see `Trading::RiskManager` and `Trading::Broker#place_bracket_order`).

## Setup

1. `bundle install` and `cp .env.example .env` — set `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`.
2. `bin/rails db:prepare`
3. Manual tick: `bin/rails trading:tick`
4. Cron: run `scripts/run_bot_cron.sh` every minute during market hours (see `README.md`).

## Constraints

- Do **not** point the broker at live Alpaca (`paper_trading` in `trading.yml`) unless the user explicitly asks.
- Never commit `.env` or real keys.
- Always use bracket orders for entries; run `pre_trade_check` before buys.
- Prefer **service objects** under `app/services/trading/` for new logic.

## Market data feed

`Trading::Broker` requests `feed=sip` for daily bars. If your Alpaca subscription rejects SIP on paper, switch to `iex` in `broker.rb` for that request.

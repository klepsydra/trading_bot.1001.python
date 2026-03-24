# CLAUDE PROJECT INSTRUCTIONS — Momentum Trading Bot (`trading_bot.1001`)

## Project language
**Core language: Ruby** — prefer Ruby (and Rails 8 patterns from `.cursor/rules`) for new features, libraries, and refactors. The **Alpaca execution path** below is still implemented in **Python** (`bot.py`, `config/`, `strategies/`, etc.) until ported.

## Overview
This repository includes a Python algorithmic trading bot using **Alpaca Markets paper trading**.
It monitors unleveraged base ETF tickers for momentum signals and executes trades
on their leveraged counterparts.

## Ticker Pairs
| Base (signal) | Leveraged ETF (traded) | Leverage |
|---------------|------------------------|----------|
| QQQ           | TQQQ                   | 3×       |
| SPY           | SPYU                   | 4×       |
| IWM           | TNA                    | 3×       |
| DIA           | UDOW                   | 3×       |

## Signal Engine (`strategies/signals.py`)
Composite score = weighted sum of four components:

| Component       | Weight | Description |
|-----------------|--------|-------------|
| Z-score         | 35%    | 1-day return normalised by 20-day rolling stddev |
| RSI             | 25%    | Scaled to [−1, +1]; oversold → +1, overbought → −1 |
| Volume          | 20%    | Spike confidence multiplier (0–1) |
| EMA crossover   | 20%    | Fast (9) vs Slow (21) EMA percentage gap |

- **BUY**  when score ≥  +0.40
- **SELL** when score ≤  −0.40
- **HOLD** otherwise

## Risk Controls (`risk/risk_manager.py`)
1. **Daily drawdown halt**: if portfolio drops ≥5% intraday → stop all trading
2. **Stop-loss**: 7% below entry (bracket order)
3. **Take-profit**: 15% above entry (bracket order)
4. **Max portfolio allocation**: 20% per position
5. **Fractional Kelly sizing**: scaled by signal strength and 1-day volatility

## Project Files
```
bot.py                      ← entry point
config/settings.py          ← all tuneable parameters + API keys
strategies/signals.py       ← signal computation
risk/risk_manager.py        ← position sizing + drawdown checks
core/broker.py              ← Alpaca API wrapper
utils/trade_logger.py       ← CSV + structured logging
requirements.txt
```

## Setup
1. Open `config/settings.py` and set `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`
   (or export them as environment variables).
2. `pip install -r requirements.txt`
3. `python bot.py`

## Key Library: alpaca-py
- `TradingClient(api_key, secret_key, paper=True)` — orders & account
- `StockHistoricalDataClient(api_key, secret_key)` — historical bars
- All orders are **bracket orders** (market entry + SL + TP).
- Only whole shares are used (no fractional for leveraged ETFs).
- Base URLs are handled automatically by `paper=True`.

## Constraints Claude Must Respect
- NEVER generate code that sets `paper=False` unless explicitly requested.
- NEVER hardcode API keys; always use environment variables or `config/settings.py`.
- ALWAYS use bracket orders so every trade has a stop-loss.
- ALWAYS perform `pre_trade_check` before order submission.
- Risk parameters in `config/settings.py` are the single source of truth.
- Do not change `STOP_LOSS_PCT` below 0.05 or `MAX_DAILY_DRAWDOWN_PCT` below 0.03.

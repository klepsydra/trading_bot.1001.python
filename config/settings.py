"""
Configuration settings for the Momentum Trading Bot (legacy Python runner; repository core language is Ruby).
Add your Alpaca paper trading API keys below.
NEVER commit real keys to version control.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ─── Alpaca API Credentials ───────────────────────────────────────────────────
# Set these via environment variables or replace the defaults with your paper keys.
ALPACA_API_KEY    = os.environ.get("ALPACA_API_KEY",    "YOUR_PAPER_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "YOUR_PAPER_SECRET_KEY")
PAPER_TRADING     = True   # Always True until you are ready for live trading

# ─── Ticker Pairs  (base → leveraged ETF)  ────────────────────────────────────
# base ticker is used for signal calculation; leveraged ETF is traded.
TICKER_PAIRS = {
    "QQQ":  {"etf": "TQQQ", "leverage": 3},
    "SPY":  {"etf": "SPYU", "leverage": 4},
    "IWM":  {"etf": "TNA",  "leverage": 3},
    "DIA":  {"etf": "UDOW", "leverage": 3},
}

# ─── Signal Engine Parameters ─────────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "zscore":  0.35,   # stddev z-score of 1-day price move
    "rsi":     0.25,   # RSI component
    "volume":  0.20,   # volume spike confidence multiplier
    "ema":     0.20,   # EMA crossover
}

BUY_THRESHOLD  =  0.40   # composite score to trigger a BUY
SELL_THRESHOLD = -0.40   # composite score to trigger a SELL (or close long)

# RSI settings
RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# EMA periods
EMA_FAST        = 9
EMA_SLOW        = 21

# Z-score lookback (trading days)
ZSCORE_LOOKBACK = 20

# Volume spike threshold (x times 20-day average)
VOLUME_SPIKE_MULTIPLIER = 1.5

# Number of historical daily bars to fetch
HISTORICAL_BARS = 60

# ─── Risk Management ──────────────────────────────────────────────────────────
MAX_DAILY_DRAWDOWN_PCT  = 0.05   # 5% — halt trading if portfolio drops this much in a day
STOP_LOSS_PCT           = 0.07   # 7%  stop-loss per position
TAKE_PROFIT_PCT         = 0.15   # 15% take-profit per position
MAX_PORTFOLIO_ALLOC_PCT = 0.20   # 20% max of portfolio per single position
KELLY_FRACTION          = 0.25   # fractional Kelly scaling

# ─── Execution ────────────────────────────────────────────────────────────────
LOOP_INTERVAL_SECONDS = 60       # how often the main loop runs (seconds)
MARKET_OPEN_HOUR      = 9        # 9:30 ET
MARKET_OPEN_MINUTE    = 30
MARKET_CLOSE_HOUR     = 15       # 3:45 ET — exit before close
MARKET_CLOSE_MINUTE   = 45

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_FILE = "logs/trading_bot.log"
TRADE_LOG_FILE = "logs/trades.csv"

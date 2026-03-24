"""
bot.py
─────────────────────────────────────────────────────────────────────────────
Momentum Trading Bot — Alpaca Paper Trading (legacy Python runner; repo Ruby-first)
─────────────────────────────────────────────────────────────────────────────

Strategy:
  • Monitor QQQ, SPY, IWM, DIA (unleveraged base tickers).
  • Compute momentum signals (z-score, RSI, EMA, volume) on each base.
  • Execute on leveraged ETF counterparts: TQQQ, SPYU, TNA, UDOW.
  • Risk checks before every order; bracket orders (SL + TP) always used.
  • 5% daily drawdown → halt all trading for the rest of the day.

Run:
    python bot.py
"""

import logging
import time
from datetime import datetime, timezone

from config.settings import (
    TICKER_PAIRS,
    LOOP_INTERVAL_SECONDS,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    HISTORICAL_BARS,
    LOG_FILE,
    TRADE_LOG_FILE,
)
from core.broker import Broker
from strategies.signals import compute_signal
from risk.risk_manager import RiskManager
from utils.trade_logger import setup_logging, TradeLogger
from alpaca.trading.enums import OrderSide

setup_logging(LOG_FILE)
log = logging.getLogger("bot")


# ── Helpers ───────────────────────────────────────────────────────────────────

def within_trading_window() -> bool:
    """Return True during the allowed trading window (in US/Eastern approx)."""
    now = datetime.now(timezone.utc)
    # Crude offset: UTC−5 (EST). Adjust for DST if needed.
    et_hour   = (now.hour - 5) % 24
    et_minute = now.minute
    after_open  = (et_hour, et_minute) >= (MARKET_OPEN_HOUR,  MARKET_OPEN_MINUTE)
    before_close = (et_hour, et_minute) <= (MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    return after_open and before_close


def compute_volatility(df) -> float:
    """1-day realised volatility (std of log returns over last 20 days)."""
    import numpy as np
    closes = df["close"].values.astype(float)
    if len(closes) < 2:
        return 0.01
    returns = np.diff(np.log(closes))[-20:]
    return float(returns.std(ddof=1)) if len(returns) > 1 else 0.01


# ── Main loop ─────────────────────────────────────────────────────────────────

def run():
    log.info("═" * 60)
    log.info("  Momentum Trading Bot starting up (Python runner)")
    log.info("═" * 60)

    broker       = Broker()
    risk_manager = RiskManager(broker)
    trade_logger = TradeLogger(TRADE_LOG_FILE)

    while True:
        try:
            loop_iteration(broker, risk_manager, trade_logger)
        except KeyboardInterrupt:
            log.info("Shutdown requested — closing all positions.")
            broker.cancel_all_orders()
            break
        except Exception as exc:
            log.error("Unhandled error in main loop: %s", exc, exc_info=True)

        time.sleep(LOOP_INTERVAL_SECONDS)


def loop_iteration(broker: Broker, risk: RiskManager, tlog: TradeLogger):
    if not broker.is_market_open():
        log.debug("Market closed — sleeping.")
        return

    if not within_trading_window():
        log.info("Outside trading window — skipping.")
        return

    # ── Daily drawdown halt ───────────────────────────────────────────────────
    if risk.daily_drawdown_breached():
        log.warning("Trading HALTED for the day (drawdown limit reached).")
        return

    positions = broker.get_positions()

    for base_symbol, pair in TICKER_PAIRS.items():
        etf_symbol = pair["etf"]

        try:
            # 1. Fetch historical bars for the BASE ticker (signal)
            df = broker.get_daily_bars(base_symbol, n_days=HISTORICAL_BARS)
            if df is None or len(df) < 25:
                log.warning("%s: not enough bars (%d) — skipping", base_symbol, len(df) if df is not None else 0)
                continue

            # 2. Compute momentum signal on base
            sig = compute_signal(df, symbol=base_symbol)
            action = sig["action"]

            # 3. Fetch current ETF price
            etf_price = broker.get_latest_price(etf_symbol)

            # 4. Volatility of base (for sizing)
            vol = compute_volatility(df)

            # 5. Execute signal
            existing_position = positions.get(etf_symbol)

            if action == "BUY" and not existing_position:
                shares = risk.calc_position_size(sig["score"], etf_price, vol)
                if risk.pre_trade_check(etf_symbol, shares, etf_price):
                    order = broker.place_bracket_order(
                        symbol=etf_symbol,
                        qty=shares,
                        side=OrderSide.BUY,
                        entry_price=etf_price,
                    )
                    tlog.record(
                        base_symbol=base_symbol,
                        etf_symbol=etf_symbol,
                        action="BUY",
                        shares=shares,
                        entry_price=etf_price,
                        stop_price=round(etf_price * 0.93, 2),
                        take_profit_price=round(etf_price * 1.15, 2),
                        signal_score=sig["score"],
                        z_score=sig["z_score"],
                        rsi_signal=sig["rsi_signal"],
                        ema_signal=sig["ema_signal"],
                        vol_conf=sig["vol_conf"],
                        portfolio_value=broker.get_portfolio_value(),
                        order_id=order.id if order else "",
                    )

            elif action == "SELL" and existing_position:
                broker.close_position(etf_symbol)
                tlog.record(
                    base_symbol=base_symbol,
                    etf_symbol=etf_symbol,
                    action="SELL/CLOSE",
                    shares=existing_position.qty,
                    entry_price=etf_price,
                    signal_score=sig["score"],
                    z_score=sig["z_score"],
                    rsi_signal=sig["rsi_signal"],
                    ema_signal=sig["ema_signal"],
                    vol_conf=sig["vol_conf"],
                    portfolio_value=broker.get_portfolio_value(),
                )

            else:
                log.info("HOLD | %s → %s | score=%.4f", base_symbol, etf_symbol, sig["score"])

        except Exception as exc:
            log.error("Error processing pair %s→%s: %s", base_symbol, etf_symbol, exc, exc_info=True)


if __name__ == "__main__":
    run()

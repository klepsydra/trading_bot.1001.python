"""
risk/risk_manager.py
Pre-trade risk checks and position sizing.

Controls:
  1. Max daily drawdown halt       (5%)
  2. Max portfolio allocation      (20% per position)
  3. Fractional Kelly position size
  4. Stop-loss / take-profit baked into bracket orders (see broker.py)
"""

import logging
from datetime import date

from config.settings import (
    MAX_DAILY_DRAWDOWN_PCT,
    MAX_PORTFOLIO_ALLOC_PCT,
    KELLY_FRACTION,
)

log = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, broker):
        self.broker = broker
        self._start_of_day_value: float | None = None
        self._start_date: date | None = None

    # ── Daily drawdown tracking ───────────────────────────────────────────────

    def _refresh_day_start(self):
        today = date.today()
        if self._start_date != today:
            self._start_date = today
            self._start_of_day_value = self.broker.get_portfolio_value()
            log.info("Day start portfolio value: $%.2f", self._start_of_day_value)

    def daily_drawdown_breached(self) -> bool:
        """Return True if today's drawdown exceeds the halt threshold."""
        self._refresh_day_start()
        current = self.broker.get_portfolio_value()
        if self._start_of_day_value and self._start_of_day_value > 0:
            drawdown = (self._start_of_day_value - current) / self._start_of_day_value
            if drawdown >= MAX_DAILY_DRAWDOWN_PCT:
                log.warning(
                    "DAILY DRAWDOWN HALT: %.2f%% drawdown (limit %.2f%%)",
                    drawdown * 100, MAX_DAILY_DRAWDOWN_PCT * 100,
                )
                return True
        return False

    # ── Position sizing ───────────────────────────────────────────────────────

    def calc_position_size(
        self,
        signal_score: float,
        entry_price: float,
        volatility: float,
    ) -> int:
        """
        Fractional Kelly sizing scaled by signal strength and volatility.

        Kelly fraction (simplified, no win/loss ratio):
            f* = KELLY_FRACTION * |signal_score|

        Volatility scaling: scale down when 1-day stddev is high.
        Returns whole number of shares (leveraged ETFs don't support fractions).
        """
        portfolio_value = self.broker.get_portfolio_value()
        max_dollar_alloc = portfolio_value * MAX_PORTFOLIO_ALLOC_PCT

        # Kelly scalar: stronger signal → larger fraction, max = KELLY_FRACTION
        kelly_scalar = KELLY_FRACTION * min(abs(signal_score) / 1.0, 1.0)

        # Volatility damper: if 1-day stddev > 2%, shrink size
        vol_damper = 1.0
        if volatility > 0:
            vol_damper = min(0.02 / volatility, 1.0)

        dollar_size = portfolio_value * kelly_scalar * vol_damper
        dollar_size = min(dollar_size, max_dollar_alloc)

        shares = int(dollar_size / entry_price)

        log.info(
            "SIZING | portfolio=$%.0f kelly=%.3f vol_damper=%.3f "
            "dollar=$%.0f shares=%d @ $%.2f",
            portfolio_value, kelly_scalar, vol_damper, dollar_size, shares, entry_price,
        )
        return max(shares, 0)

    # ── Pre-trade gate ────────────────────────────────────────────────────────

    def pre_trade_check(
        self,
        symbol: str,
        shares: int,
        entry_price: float,
    ) -> bool:
        """
        Final go/no-go before submitting an order.
        Returns True if trade is allowed.
        """
        if shares <= 0:
            log.warning("PRE-TRADE REJECT | %s | shares=%d (zero)", symbol, shares)
            return False

        buying_power = self.broker.get_buying_power()
        required = shares * entry_price
        if required > buying_power:
            log.warning(
                "PRE-TRADE REJECT | %s | need $%.0f but buying power $%.0f",
                symbol, required, buying_power,
            )
            return False

        portfolio_value = self.broker.get_portfolio_value()
        alloc_pct = required / portfolio_value
        if alloc_pct > MAX_PORTFOLIO_ALLOC_PCT:
            log.warning(
                "PRE-TRADE REJECT | %s | alloc %.1f%% exceeds limit %.1f%%",
                symbol, alloc_pct * 100, MAX_PORTFOLIO_ALLOC_PCT * 100,
            )
            return False

        log.info("PRE-TRADE OK | %s | %d shares @ $%.2f", symbol, shares, entry_price)
        return True

"""
core/broker.py
Thin wrapper around alpaca-py TradingClient & StockHistoricalDataClient.
All order placement and account queries go through here.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

from config.settings import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    PAPER_TRADING,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
)

log = logging.getLogger(__name__)


class Broker:
    """Handles all Alpaca API interactions."""

    def __init__(self):
        self.trading = TradingClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
            paper=PAPER_TRADING,
        )
        self.data = StockHistoricalDataClient(
            api_key=ALPACA_API_KEY,
            secret_key=ALPACA_SECRET_KEY,
        )
        log.info("Broker initialised (paper=%s)", PAPER_TRADING)

    # ── Account ───────────────────────────────────────────────────────────────

    def get_account(self):
        return self.trading.get_account()

    def get_portfolio_value(self) -> float:
        acct = self.get_account()
        return float(acct.portfolio_value)

    def get_buying_power(self) -> float:
        acct = self.get_account()
        return float(acct.buying_power)

    def get_positions(self) -> Dict[str, object]:
        """Returns {symbol: position_object}."""
        positions = self.trading.get_all_positions()
        return {p.symbol: p for p in positions}

    def get_position(self, symbol: str) -> Optional[object]:
        positions = self.get_positions()
        return positions.get(symbol)

    # ── Market Data ───────────────────────────────────────────────────────────

    def get_daily_bars(self, symbol: str, n_days: int = 60):
        """Fetch last n_days of daily bars; returns a pandas DataFrame."""
        start = datetime.now(timezone.utc) - timedelta(days=n_days + 10)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
        )
        bars = self.data.get_stock_bars(req)
        df = bars.df
        if isinstance(df.index, type(None)):
            return df
        # flatten multi-index if necessary
        if hasattr(df.index, "levels"):
            df = df.xs(symbol, level="symbol") if symbol in df.index.get_level_values("symbol") else df
        return df.tail(n_days)

    def get_latest_price(self, symbol: str) -> float:
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = self.data.get_stock_latest_quote(req)
        return float(quote[symbol].ask_price)

    def is_market_open(self) -> bool:
        clock = self.trading.get_clock()
        return clock.is_open

    # ── Orders ────────────────────────────────────────────────────────────────

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        entry_price: float,
    ):
        """
        Submit a market bracket order with automatic stop-loss & take-profit.
        Bracket orders require fractional=False for most leveraged ETFs.
        """
        if side == OrderSide.BUY:
            stop_price   = round(entry_price * (1 - STOP_LOSS_PCT), 2)
            profit_price = round(entry_price * (1 + TAKE_PROFIT_PCT), 2)
        else:
            stop_price   = round(entry_price * (1 + STOP_LOSS_PCT), 2)
            profit_price = round(entry_price * (1 - TAKE_PROFIT_PCT), 2)

        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=int(qty),           # whole shares only for leveraged ETFs
            side=side,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=profit_price),
            stop_loss=StopLossRequest(stop_price=stop_price),
        )

        try:
            order = self.trading.submit_order(order_data)
            log.info(
                "ORDER SUBMITTED | %s %s %d @ ~%.2f | SL=%.2f TP=%.2f | id=%s",
                side.value.upper(), symbol, int(qty), entry_price,
                stop_price, profit_price, order.id,
            )
            return order
        except Exception as exc:
            log.error("Order submission failed for %s: %s", symbol, exc)
            raise

    def close_position(self, symbol: str):
        """Market-close an existing position."""
        try:
            result = self.trading.close_position(symbol)
            log.info("POSITION CLOSED | %s", symbol)
            return result
        except Exception as exc:
            log.error("Failed to close position %s: %s", symbol, exc)
            raise

    def cancel_all_orders(self):
        self.trading.cancel_orders()
        log.info("All open orders cancelled.")

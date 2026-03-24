"""
utils/trade_logger.py
Structured CSV trade log + console/file logger setup.
"""

import csv
import logging
import os
from datetime import datetime


def setup_logging(log_file: str = "logs/trading_bot.log"):
    os.makedirs("logs", exist_ok=True)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


class TradeLogger:
    FIELDS = [
        "timestamp", "base_symbol", "etf_symbol", "action",
        "shares", "entry_price", "stop_price", "take_profit_price",
        "signal_score", "z_score", "rsi_signal", "ema_signal", "vol_conf",
        "portfolio_value", "order_id",
    ]

    def __init__(self, path: str = "logs/trades.csv"):
        os.makedirs("logs", exist_ok=True)
        self.path = path
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=self.FIELDS).writeheader()
        self.log = logging.getLogger("TradeLogger")

    def record(self, **kwargs):
        row = {"timestamp": datetime.utcnow().isoformat()} | kwargs
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS, extrasaction="ignore")
            writer.writerow(row)
        self.log.info("TRADE LOGGED | %s", row)

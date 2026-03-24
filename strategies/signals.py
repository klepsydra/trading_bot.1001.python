"""
strategies/signals.py
Momentum signal engine.

Composite score = weighted sum of:
  • Z-score of today's 1-day return (stddev normalised over ZSCORE_LOOKBACK days)
  • RSI component  (−1 … +1 scale)
  • EMA crossover  (binary ±1 scaled by signal strength)
  • Volume spike   (confidence multiplier, 0 … 1)

Final score is in roughly [−1, +1].
Buy  when score ≥  BUY_THRESHOLD
Sell when score ≤  SELL_THRESHOLD
"""

import logging
import numpy as np
import pandas as pd

from config.settings import (
    SIGNAL_WEIGHTS,
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    RSI_PERIOD,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    EMA_FAST,
    EMA_SLOW,
    ZSCORE_LOOKBACK,
    VOLUME_SPIKE_MULTIPLIER,
)

log = logging.getLogger(__name__)


# ── Individual indicators ─────────────────────────────────────────────────────

def compute_zscore(df: pd.DataFrame, lookback: int = ZSCORE_LOOKBACK) -> float:
    """
    Z-score of today's 1-day return relative to the rolling mean/std
    of the lookback window.  Capped at ±3 and rescaled to [−1, +1].
    """
    closes = df["close"].values.astype(float)
    if len(closes) < lookback + 1:
        return 0.0
    returns = np.diff(np.log(closes))          # log returns
    window  = returns[-lookback:]
    mu      = window.mean()
    sigma   = window.std(ddof=1)
    if sigma == 0:
        return 0.0
    today_return = returns[-1]
    z = (today_return - mu) / sigma
    z = float(np.clip(z, -3, 3))
    return z / 3.0                             # normalise to [−1, +1]


def compute_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> float:
    """
    Standard RSI.  Returns a signal in [−1, +1]:
      −1  = extremely overbought (want to sell)
      +1  = extremely oversold   (want to buy)
    """
    closes = df["close"].values.astype(float)
    if len(closes) < period + 1:
        return 0.0
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs  = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    # Map RSI to [−1, +1]: oversold (+1 bullish), overbought (−1 bearish)
    if rsi >= RSI_OVERBOUGHT:
        return -((rsi - RSI_OVERBOUGHT) / (100 - RSI_OVERBOUGHT))
    elif rsi <= RSI_OVERSOLD:
        return  (RSI_OVERSOLD - rsi) / RSI_OVERSOLD
    else:
        # Neutral zone — mild directional lean
        midpoint = (RSI_OVERBOUGHT + RSI_OVERSOLD) / 2
        return (rsi - midpoint) / (midpoint - RSI_OVERSOLD) * -0.3


def compute_ema_signal(df: pd.DataFrame) -> float:
    """
    Fast EMA vs Slow EMA crossover.
    Returns +1 if fast > slow (bullish), −1 otherwise,
    scaled by the percentage gap between the two EMAs.
    """
    closes = df["close"]
    if len(closes) < EMA_SLOW + 1:
        return 0.0
    ema_fast = closes.ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
    ema_slow = closes.ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
    pct_gap  = (ema_fast - ema_slow) / ema_slow
    signal   = float(np.sign(pct_gap) * min(abs(pct_gap) * 50, 1.0))
    return signal


def compute_volume_confidence(df: pd.DataFrame) -> float:
    """
    Volume spike confidence:  today's volume vs 20-day average.
    Returns 0 … 1.  Values > VOLUME_SPIKE_MULTIPLIER score higher.
    """
    vols = df["volume"].values.astype(float)
    if len(vols) < 21:
        return 0.5
    avg_vol   = vols[-21:-1].mean()
    today_vol = vols[-1]
    if avg_vol == 0:
        return 0.5
    ratio = today_vol / avg_vol
    # scale: ratio of 1.0 → confidence 0.5; ratio of MULTIPLIER → 1.0
    confidence = min(ratio / (2 * VOLUME_SPIKE_MULTIPLIER), 1.0)
    return confidence


# ── Composite score ───────────────────────────────────────────────────────────

def compute_signal(df: pd.DataFrame, symbol: str = "") -> dict:
    """
    Returns a dict with the composite score and each sub-component.
    score > BUY_THRESHOLD  → BUY
    score < SELL_THRESHOLD → SELL
    otherwise              → HOLD
    """
    z        = compute_zscore(df)
    rsi_sig  = compute_rsi(df)
    ema_sig  = compute_ema_signal(df)
    vol_conf = compute_volume_confidence(df)

    w = SIGNAL_WEIGHTS
    # Volume confidence acts as a multiplier on directional signals
    directional = (
        w["zscore"] * z +
        w["rsi"]    * rsi_sig +
        w["ema"]    * ema_sig
    )
    volume_weight = w["volume"]
    score = directional * (1 - volume_weight) + directional * vol_conf * volume_weight

    if score >= BUY_THRESHOLD:
        action = "BUY"
    elif score <= SELL_THRESHOLD:
        action = "SELL"
    else:
        action = "HOLD"

    result = {
        "symbol":      symbol,
        "score":       round(score, 4),
        "action":      action,
        "z_score":     round(z, 4),
        "rsi_signal":  round(rsi_sig, 4),
        "ema_signal":  round(ema_sig, 4),
        "vol_conf":    round(vol_conf, 4),
    }
    log.info("SIGNAL | %s | score=%.4f action=%s | z=%.3f rsi=%.3f ema=%.3f vol=%.3f",
             symbol, score, action, z, rsi_sig, ema_sig, vol_conf)
    return result

"""
Market regime detector — classifies current market conditions from OHLCV data.

Uses the last 200 candles for the given pair/timeframe.
Computes:
  - 50-period SMA slope → trend direction
  - ATR(14) / price ratio → volatility level
  - Combined → regime label
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.services.ohlcv_loader import load_ohlcv
from app.core.config import DEFAULT_EXCHANGE


@dataclass
class RegimeResult:
    regime: str            # bull_trending | bear_trending | sideways_low_vol | sideways_high_vol | volatile
    trend_direction: str   # up | down | flat
    volatility_level: str  # low | medium | high
    confidence: float      # 0–1
    details: dict


async def detect_regime(
    pair: str,
    timeframe: str,
    exchange: str = DEFAULT_EXCHANGE,
) -> RegimeResult:
    candles = load_ohlcv(pair, timeframe, exchange)
    candles = candles[-200:]  # last 200 candles

    if len(candles) < 20:
        return RegimeResult(
            regime="unknown",
            trend_direction="flat",
            volatility_level="medium",
            confidence=0.0,
            details={"reason": "insufficient_data", "candle_count": len(candles)},
        )

    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    # ── 50-period SMA slope ───────────────────────────────────────────────────
    sma_window = min(50, len(closes))
    sma_recent = statistics.mean(closes[-sma_window:])
    sma_older  = statistics.mean(closes[-sma_window: -sma_window // 2] or closes[:sma_window // 2])
    slope_pct  = (sma_recent - sma_older) / max(sma_older, 1e-9) * 100

    if slope_pct > 1.0:
        trend_direction = "up"
    elif slope_pct < -1.0:
        trend_direction = "down"
    else:
        trend_direction = "flat"

    # ── ATR(14) / price ratio ─────────────────────────────────────────────────
    atr_period = min(14, len(candles) - 1)
    true_ranges: list[float] = []
    for i in range(1, atr_period + 1):
        idx = len(candles) - i
        tr = max(
            highs[idx] - lows[idx],
            abs(highs[idx] - closes[idx - 1]),
            abs(lows[idx]  - closes[idx - 1]),
        )
        true_ranges.append(tr)

    atr = statistics.mean(true_ranges) if true_ranges else 0.0
    price = closes[-1] or 1.0
    atr_ratio = atr / price * 100  # as % of price

    if atr_ratio < 0.5:
        volatility_level = "low"
    elif atr_ratio < 1.5:
        volatility_level = "medium"
    else:
        volatility_level = "high"

    # ── Regime classification ─────────────────────────────────────────────────
    if trend_direction == "up" and volatility_level in ("low", "medium"):
        regime = "bull_trending"
    elif trend_direction == "down" and volatility_level in ("low", "medium"):
        regime = "bear_trending"
    elif trend_direction == "flat" and volatility_level == "low":
        regime = "sideways_low_vol"
    elif trend_direction == "flat" and volatility_level in ("medium", "high"):
        regime = "sideways_high_vol"
    else:
        regime = "volatile"

    # Confidence: higher when slope and ATR are unambiguous
    slope_confidence = min(abs(slope_pct) / 3.0, 1.0)
    vol_confidence   = min(atr_ratio / 1.5, 1.0) if volatility_level == "high" else 0.7
    confidence = round((slope_confidence + vol_confidence) / 2, 2)

    return RegimeResult(
        regime=regime,
        trend_direction=trend_direction,
        volatility_level=volatility_level,
        confidence=confidence,
        details={
            "sma_slope_pct": round(slope_pct, 4),
            "atr_ratio_pct": round(atr_ratio, 4),
            "candle_count": len(candles),
            "last_close": round(price, 6),
        },
    )

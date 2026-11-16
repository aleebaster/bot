"""Candlestick pattern recognition with market-context filters.

Patterns are evaluated only on closed candles. A pattern without a supporting
context (prior trend) is deliberately not reported as a tradable signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.market_data.models import Candle

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class CandleMetrics:
    body: float
    upper_wick: float
    lower_wick: float
    candle_range: float
    body_ratio: float
    is_bullish: bool
    is_bearish: bool


@dataclass(frozen=True)
class PatternSignal:
    name: str
    direction: str
    strength: float  # 0..1
    context_confirmed: bool


def metrics(candle: Candle) -> CandleMetrics:
    body = abs(candle.close - candle.open)
    upper = candle.high - max(candle.open, candle.close)
    lower = min(candle.open, candle.close) - candle.low
    candle_range = max(candle.high - candle.low, 1e-12)
    return CandleMetrics(
        body=body,
        upper_wick=max(upper, 0.0),
        lower_wick=max(lower, 0.0),
        candle_range=candle_range,
        body_ratio=body / candle_range,
        is_bullish=candle.close > candle.open,
        is_bearish=candle.close < candle.open,
    )


def recent_trend(candles: list[Candle], lookback: int = 6) -> int:
    """-1 downtrend, 0 neutral/ranging, +1 uptrend over recent closes."""
    closes = [c.close for c in candles[-lookback:]]
    if len(closes) < 3:
        return 0
    delta = closes[-1] - closes[0]
    noise = sum(abs(b - a) for a, b in zip(closes, closes[1:])) / max(len(closes) - 1, 1)
    if delta > noise * 0.6:
        return 1
    if delta < -noise * 0.6:
        return -1
    return 0


def _add(out: list[PatternSignal], name: str, direction: str, strength: float, confirmed: bool) -> None:
    out.append(PatternSignal(name, direction, min(1.0, max(0.0, strength)), confirmed))


def detect_patterns(candles: list[Candle]) -> list[PatternSignal]:
    """Detect patterns ending at the last (closed) candle."""
    out: list[PatternSignal] = []
    if not candles:
        return out

    cur = candles[-1]
    m = metrics(cur)
    trend = recent_trend(candles[:-1])
    prev = candles[-2] if len(candles) >= 2 else None
    prev2 = candles[-3] if len(candles) >= 3 else None
    prev3 = candles[-4] if len(candles) >= 4 else None
    pm = metrics(prev) if prev else None

    # --- Doji ---------------------------------------------------------------
    if m.body_ratio <= 0.1:
        _add(out, "Doji", NEUTRAL, 0.35 + (0.1 - m.body_ratio), False)

    # --- Hammer / Shooting Star / Pin Bar / strong rejection ----------------
    if m.body > 0:
        if m.lower_wick >= 2 * m.body and m.upper_wick <= m.body * 1.1 and m.body_ratio <= 0.45:
            confirmed = trend <= 0
            _add(out, "Hammer", BULLISH, 0.65 + 0.2 * min(1.0, m.lower_wick / m.candle_range), confirmed)
        if m.upper_wick >= 2 * m.body and m.lower_wick <= m.body * 1.1 and m.body_ratio <= 0.45:
            confirmed = trend >= 0
            _add(out, "Shooting Star", BEARISH, 0.65 + 0.2 * min(1.0, m.upper_wick / m.candle_range), confirmed)
        if m.lower_wick >= 2.5 * m.body and m.lower_wick >= 0.55 * m.candle_range:
            _add(out, "Pin Bar", BULLISH, 0.6, trend <= 0)
        if m.upper_wick >= 2.5 * m.body and m.upper_wick >= 0.55 * m.candle_range:
            _add(out, "Pin Bar", BEARISH, 0.6, trend >= 0)
        if m.lower_wick >= 2 * m.body and m.lower_wick >= 0.5 * m.candle_range and cur.close > cur.open:
            _add(out, "Strong Rejection", BULLISH, 0.6, trend <= 0)
        if m.upper_wick >= 2 * m.body and m.upper_wick >= 0.5 * m.candle_range and cur.close < cur.open:
            _add(out, "Strong Rejection", BEARISH, 0.6, trend >= 0)

    # --- Engulfing ----------------------------------------------------------
    if prev and pm and pm.body > 0:
        if pm.is_bearish and m.is_bullish and cur.open <= prev.close and cur.close >= prev.open:
            _add(out, "Bullish Engulfing", BULLISH, 0.8, trend <= 0)
        if pm.is_bullish and m.is_bearish and cur.open >= prev.close and cur.close <= prev.open:
            _add(out, "Bearish Engulfing", BEARISH, 0.8, trend >= 0)

    # --- Inside / Outside bar ----------------------------------------------
    if prev:
        if cur.high < prev.high and cur.low > prev.low:
            _add(out, "Inside Bar", NEUTRAL, 0.35, False)
        if cur.high > prev.high and cur.low < prev.low:
            _add(out, "Outside Bar", BULLISH if m.is_bullish else BEARISH, 0.45, False)

    # --- Morning / Evening Star --------------------------------------------
    if prev and prev2:
        first, middle, last = prev2, prev, cur
        fm, mm = metrics(first), metrics(middle)
        if fm.is_bearish and fm.body_ratio > 0.4 and mm.body_ratio < 0.35 and last.close > (first.open + first.close) / 2:
            _add(out, "Morning Star", BULLISH, 0.85, trend <= 0)
        if fm.is_bullish and fm.body_ratio > 0.4 and mm.body_ratio < 0.35 and last.close < (first.open + first.close) / 2:
            _add(out, "Evening Star", BEARISH, 0.85, trend >= 0)

    # --- Three White Soldiers / Three Black Crows --------------------------
    if prev and prev2:
        three = [prev2, prev, cur]
        if all(metrics(c).is_bullish and metrics(c).body_ratio > 0.35 for c in three):
            if three[1].close > three[0].close and three[2].close > three[1].close:
                _add(out, "Three White Soldiers", BULLISH, 0.75, trend <= 0)
        if all(metrics(c).is_bearish and metrics(c).body_ratio > 0.35 for c in three):
            if three[1].close < three[0].close and three[2].close < three[1].close:
                _add(out, "Three Black Crows", BEARISH, 0.75, trend >= 0)

    # --- Next-candle confirmation hint -------------------------------------
    if prev3 and prev2 and prev and prev2.close < min(prev3.close, prev.close) and cur.close > prev2.close:
        _add(out, "Bullish Confirmation", BULLISH, 0.3, True)
    if prev3 and prev2 and prev and prev2.close > max(prev3.close, prev.close) and cur.close < prev2.close:
        _add(out, "Bearish Confirmation", BEARISH, 0.3, True)

    out.sort(key=lambda p: p.strength, reverse=True)
    return out


def best_pattern(candles: list[Candle], direction: str | None = None) -> PatternSignal | None:
    patterns = detect_patterns(candles)
    if direction:
        patterns = [p for p in patterns if p.direction == direction]
    return patterns[0] if patterns else None

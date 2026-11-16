"""Candlestick confirmation with closed-bar, volume, level and follow-through checks."""

from __future__ import annotations

from app.candle_patterns.detector import BEARISH, BULLISH, detect_patterns, metrics
from app.constants import LONG, SHORT
from app.false_signal.models import CandleConfirmationResult


def confirm_candle(
    candles: list,
    direction: str,
    pa,
    relative_volume: float,
    atr: float,
) -> CandleConfirmationResult:
    result = CandleConfirmationResult()
    if len(candles) < 2:
        result.detail = "Insufficient candles"
        return result

    last = candles[-1]
    result.closed = bool(last.closed)
    if not result.closed:
        result.detail = "Last candle is not closed - no confirmation"
        return result

    wanted = BULLISH if direction == LONG else BEARISH
    current_patterns = detect_patterns(candles[-4:])
    previous_patterns = detect_patterns(candles[-5:-1])
    result.patterns = [p.name for p in current_patterns]

    matching = [p for p in current_patterns if p.direction == wanted]
    result.direction_match = bool(matching)
    m = metrics(last)
    result.body_ok = bool(m.body_ratio >= 0.25 or m.upper_wick >= 1.5 * m.body or m.lower_wick >= 1.5 * m.body)
    result.volume_ok = relative_volume >= 1.0

    reference = last.close
    levels = (pa.supports if direction == LONG else pa.resistances)
    result.near_level = bool(levels and abs(reference - levels[0].price) / max(reference, 1e-9) <= 0.015)

    prior_matching = [p for p in previous_patterns if p.direction == wanted]
    if prior_matching and len(candles) >= 2:
        follow = last.close > candles[-2].close if direction == LONG else last.close < candles[-2].close
        result.next_bar_confirms = bool(follow and m.body_ratio >= 0.2)

    score = 0.0
    if result.direction_match:
        score += 6
    if matching and matching[0].context_confirmed:
        score += 2
    if result.body_ok:
        score += 2
    if result.volume_ok:
        score += 2
    if result.near_level:
        score += 2
    if result.next_bar_confirms:
        score += 1
    result.score = round(min(15.0, score), 2)
    result.confirmed = bool(result.closed and result.direction_match and result.body_ok and result.volume_ok)

    result.detail = (
        f"patterns={result.patterns}, match={result.direction_match}, body={m.body_ratio:.2f}, "
        f"RV={relative_volume:.2f}, near_level={result.near_level}, follow={result.next_bar_confirms}"
    )
    return result

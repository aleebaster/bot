"""RSI confirmation/disagreement analysis (RSI 7/14/21, never a standalone trigger)."""

from __future__ import annotations

import pandas as pd

from app.constants import LONG, SHORT
from app.false_signal.models import Finding, RSIConfirmationResult
from app.indicators.divergence import analyze_rsi, detect_divergences
from app.indicators.technical import IndicatorSet


def confirm_rsi(frame: pd.DataFrame, direction: str, timeframe: str = "15m") -> RSIConfirmationResult:
    result = RSIConfirmationResult()
    if frame.empty or len(frame) < 30:
        result.detail = "Insufficient RSI history"
        return result

    state = analyze_rsi(frame, timeframe)
    divs = detect_divergences(frame, timeframe, 14)
    indicator = IndicatorSet.from_frame(frame)
    rsi7, rsi14, rsi21 = indicator.last("rsi7"), indicator.last("rsi14"), indicator.last("rsi21")

    bull_div = any(d.kind in {"bullish", "hidden_bullish"} for d in divs)
    bear_div = any(d.kind in {"bearish", "hidden_bearish"} for d in divs)
    value = state.value

    side_ok = (
        (value is not None and value > 50) if direction == LONG
        else (value is not None and value < 50)
    )
    momentum_ok = (
        (rsi7 is not None and rsi14 is not None and rsi7 > rsi14) if direction == LONG
        else (rsi7 is not None and rsi14 is not None and rsi7 < rsi14)
    )
    cross_ok = (
        state.crossed_above_50 if direction == LONG else state.crossed_below_50
    )

    result.bullish_confirmation = bool(
        direction == LONG and ((side_ok and momentum_ok) or bull_div or cross_ok)
    )
    result.bearish_confirmation = bool(
        direction == SHORT and ((side_ok and momentum_ok) or bear_div or cross_ok)
    )
    result.divergence_warning = bool(
        (direction == LONG and bear_div) or (direction == SHORT and bull_div)
    )
    result.momentum_weakness = bool(rsi7 is not None and rsi14 is not None and not momentum_ok)
    result.false_breakout_warning = bool(result.divergence_warning and side_ok)

    if result.bullish_confirmation or result.bearish_confirmation:
        result.agreement = 1.0
    elif result.divergence_warning or result.momentum_weakness:
        result.agreement = -1.0 if result.divergence_warning else -0.5

    score = 0.0
    if side_ok:
        score += 6
        result.findings.append(Finding("RSI side confirms direction", 0.6, f"RSI14={value:.2f}"))
    if momentum_ok:
        score += 4
        result.findings.append(Finding("RSI momentum agrees", 0.4, f"RSI7={rsi7}, RSI14={rsi14}"))
    if cross_ok:
        score += 3
        result.findings.append(Finding("RSI 50 crossover", 0.4, "fresh momentum cross"))
    favorable = bull_div if direction == LONG else bear_div
    if favorable:
        score += 3
        result.findings.append(Finding("Favourable RSI divergence", 0.5, "confirmed pivot divergence"))
    if result.divergence_warning:
        score -= 5
        result.findings.append(Finding("RSI divergence warning", 0.7, "divergence conflicts with price"))
    if result.momentum_weakness and not favorable:
        score -= 3
        result.findings.append(Finding("RSI momentum weakness", 0.5, "RSI7/RSI14 alignment missing"))
    result.score = round(max(0.0, min(15.0, score)), 2)
    result.detail = (
        f"RSI7={rsi7}, RSI14={value}, RSI21={rsi21}, agreement={result.agreement:+.1f}, "
        f"divergences={[d.kind for d in divs]}"
    )
    return result

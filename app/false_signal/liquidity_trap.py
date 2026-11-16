"""Liquidity-trap / stop-hunt pattern detection (multi-evidence, never one wick)."""

from __future__ import annotations

from app.candle_patterns.detector import metrics
from app.constants import LONG, SHORT
from app.false_signal.false_breakout import FalseBreakoutResult
from app.false_signal.models import BreakoutVerdict, Finding, LiquidityTrapResult

WEIGHTS = {
    "sweep": 0.20,
    "equal_levels": 0.10,
    "false_break": 0.20,
    "wick": 0.15,
    "reversal": 0.15,
    "volume_no_continuation": 0.10,
    "failed_retest": 0.10,
}


def detect_liquidity_trap(
    candles: list,
    direction: str,
    pa,
    breakout: FalseBreakoutResult,
    atr: float,
    relative_volume: float,
) -> LiquidityTrapResult:
    """Collect independent trap evidences and weight them into a strength."""
    result = LiquidityTrapResult()
    candles = [c for c in candles if c.closed]
    if len(candles) < 3 or atr <= 0:
        return result

    last = candles[-1]
    m = metrics(last)
    findings: list[Finding] = []

    # Sweep of the most recent swing point on either side.
    recent_highs = [s.price for s in pa.swing_highs[-4:]]
    recent_lows = [s.price for s in pa.swing_lows[-4:]]
    if recent_highs and last.high > max(recent_highs) and last.close < max(recent_highs):
        findings.append(Finding("Sweep of previous high", WEIGHTS["sweep"], "high taken, close rejected", 1))
    if recent_lows and last.low < min(recent_lows) and last.close > min(recent_lows):
        findings.append(Finding("Sweep of previous low", WEIGHTS["sweep"], "low taken, close rejected", 1))

    # Equal highs / equal lows (liquidity pools).
    if len(recent_highs) >= 2 and abs(recent_highs[-1] - recent_highs[-2]) / max(recent_highs[-1], 1e-9) <= 0.003:
        findings.append(Finding("Equal highs", WEIGHTS["equal_levels"], "two nearby reaction highs", 2))
    if len(recent_lows) >= 2 and abs(recent_lows[-1] - recent_lows[-2]) / max(recent_lows[-1], 1e-9) <= 0.003:
        findings.append(Finding("Equal lows", WEIGHTS["equal_levels"], "two nearby reaction lows", 2))

    if breakout.verdict in {BreakoutVerdict.FAILED_BREAKOUT, BreakoutVerdict.STOP_HUNT_CANDIDATE}:
        label = "False support break" if direction == SHORT else "False resistance break"
        findings.append(Finding(label, WEIGHTS["false_break"], breakout.detail))
    if breakout.verdict == BreakoutVerdict.STOP_HUNT_CANDIDATE:
        findings.append(Finding("Stop hunt candidate", WEIGHTS["false_break"], breakout.detail))

    if m.body > 0 and m.upper_wick >= 2 * m.body and m.upper_wick >= 0.5 * m.candle_range:
        findings.append(Finding("Long wick rejection", WEIGHTS["wick"], "upper wick dominates the bar", 1))
    if m.body > 0 and m.lower_wick >= 2 * m.body and m.lower_wick >= 0.5 * m.candle_range:
        findings.append(Finding("Long wick rejection", WEIGHTS["wick"], "lower wick dominates the bar", 1))

    prev = candles[-3:-1]
    if len(prev) == 2:
        move = last.close - prev[0].close
        expected = 1 if direction == LONG else -1
        if move * expected < -0.5 * atr and abs(last.close - prev[-1].close) >= 0.5 * atr:
            findings.append(Finding("Rapid reversal", WEIGHTS["reversal"], "close reversed against the signal direction"))

    if relative_volume >= 1.5 and m.body_ratio <= 0.35:
        findings.append(Finding(
            "Volume spike without continuation", WEIGHTS["volume_no_continuation"],
            f"RV={relative_volume:.2f} but body/range={m.body_ratio:.2f}", 1,
        ))
    if breakout.retest and breakout.returned_inside:
        findings.append(Finding("Failed retest", WEIGHTS["failed_retest"], "retest closed back on the wrong side"))

    result.findings = findings
    result.strength = round(min(1.0, sum(f.strength for f in findings)), 3)
    result.detected = bool(findings)
    result.detail = "; ".join(f.name for f in findings) if findings else "No liquidity-trap evidence"
    return result

"""False breakout / stop-hunt detection on closed candles only."""

from __future__ import annotations

from app.candle_patterns.detector import metrics
from app.constants import LONG, SHORT
from app.false_signal.models import BreakoutVerdict, FalseBreakoutResult, Finding

LOOKBACK = 8


def _wick_rejection(candle, direction: str, atr: float) -> tuple[bool, str]:
    m = metrics(candle)
    if m.body <= 0 or atr <= 0:
        return False, ""
    wick = m.upper_wick if direction == LONG else m.lower_wick
    ratio = wick / max(m.body, 1e-12)
    share = wick / m.candle_range
    rejected = ratio >= 1.5 and share >= 0.4 and wick >= 0.3 * atr
    label = "Long upper wick rejection" if direction == LONG else "Long lower wick rejection"
    return rejected, label if rejected else ""


def detect_false_breakout(
    candles: list,
    direction: str,
    level: float | None,
    atr: float,
    relative_volume: float,
) -> FalseBreakoutResult:
    """Classify the most recent interaction with a structural level.

    A single return to the level is NOT enough to call a failed breakout: the
    detector also requires either failed volume, a rejection wick, a short
    lifetime, or a confirmed retest that held. This avoids labelling normal
    breakout-retest behaviour as false.
    """
    result = FalseBreakoutResult(verdict=BreakoutVerdict.NO_BREAKOUT, level=level)
    if not candles or level is None or level <= 0 or atr <= 0:
        return result

    window = candles[-LOOKBACK:]
    last = window[-1]
    is_long = direction == LONG
    beyond = (lambda c: c.close > level) if is_long else (lambda c: c.close < level)
    inside = (lambda c: c.close <= level) if is_long else (lambda c: c.close >= level)

    result.closed_beyond = beyond(last)

    break_index: int | None = None
    for i in range(len(window) - 1, -1, -1):
        if beyond(window[i]) and (i == 0 or inside(window[i - 1])):
            break_index = i
            break

    wick, wick_label = _wick_rejection(last, direction, atr)
    result.rejection_wick = wick
    result.volume_confirmed = relative_volume >= 1.2

    sweep = (last.high > level and last.close < level) if is_long else (
        last.low < level and last.close > level
    )

    if break_index is None:
        if sweep:
            result.verdict = BreakoutVerdict.LIQUIDITY_SWEEP
            result.findings.append(Finding("Liquidity sweep of level", 0.5, f"wick crossed {level:.8f}, close returned inside"))
            result.detail = "Wick swept the level without a closing breakout"
        else:
            result.detail = "No recent closing breakout of the reference level"
        return result

    after = window[break_index + 1 :]
    result.returned_inside = any(inside(c) for c in after)
    result.holds_level = bool(after) and all(beyond(c) for c in after)
    tolerance = 0.2 * atr
    result.retest = any(
        (c.low <= level + tolerance and c.close > level) if is_long
        else (c.high >= level - tolerance and c.close < level)
        for c in after
    )
    lifetime = len(window) - 1 - break_index
    result.short_lived = result.returned_inside and lifetime <= 3

    if sweep and wick and relative_volume >= 1.5:
        result.verdict = BreakoutVerdict.STOP_HUNT_CANDIDATE
    elif sweep:
        result.verdict = BreakoutVerdict.LIQUIDITY_SWEEP
    elif result.returned_inside:
        # A volume-backed retest that held is a normal breakout behaviour,
        # not automatically a false breakout.
        if result.volume_confirmed and result.retest and not wick and lifetime > 2:
            result.verdict = BreakoutVerdict.BREAKOUT_RETEST
        else:
            result.verdict = BreakoutVerdict.FAILED_BREAKOUT
    elif result.retest and lifetime > 0:
        result.verdict = BreakoutVerdict.BREAKOUT_RETEST
    elif result.holds_level and result.volume_confirmed:
        result.verdict = BreakoutVerdict.CONFIRMED_BREAKOUT
    else:
        result.verdict = BreakoutVerdict.NO_BREAKOUT

    if wick:
        result.findings.append(Finding(wick_label, 0.6, f"wick/body >= 1.5 and wick >= 0.3 ATR"))
    if result.returned_inside:
        result.findings.append(Finding("Close returned inside broken level", 0.5, f"level={level:.8f}"))
    if result.retest:
        result.findings.append(Finding("Retest of broken level", 0.4, "price revisited the level and closed on the correct side"))
    if not result.volume_confirmed:
        result.findings.append(Finding("Weak breakout volume", 0.4, f"RV={relative_volume:.2f} < 1.2"))
    if result.short_lived:
        result.findings.append(Finding("Short-lived breakout", 0.5, f"lasted {lifetime} bars"))

    result.detail = f"{result.verdict.value} at {level:.8f} (bars since break={lifetime})"
    return result


def breakout_score(result: FalseBreakoutResult) -> float:
    """Map the breakout verdict to the 0..10 component of Confirmation Score."""
    return {
        BreakoutVerdict.CONFIRMED_BREAKOUT: 10.0,
        BreakoutVerdict.BREAKOUT_RETEST: 8.0,
        BreakoutVerdict.NO_BREAKOUT: 5.0,
        BreakoutVerdict.LIQUIDITY_SWEEP: 3.0,
        BreakoutVerdict.FAILED_BREAKOUT: 0.0,
        BreakoutVerdict.STOP_HUNT_CANDIDATE: 0.0,
    }[result.verdict]

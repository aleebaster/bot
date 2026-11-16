"""Entry location analysis: late/early/mid-range/invalidated entry detection."""

from __future__ import annotations

import pandas as pd

from app.constants import LONG
from app.false_signal.models import EntryLocation, EntryQualityResult
from app.indicators.technical import IndicatorSet
from app.market_data.models import frame_to_candles
from app.price_action.structure import analyze as analyze_pa
from app.risk_management.position import TradePlan


def analyze_entry_quality(
    plan: TradePlan,
    frames: dict[str, pd.DataFrame],
    min_risk_reward: float,
) -> EntryQualityResult:
    result = EntryQualityResult(
        stop_atr_multiple=plan.stop_atr_multiple,
        risk_reward=plan.risk_reward,
    )
    trigger = frames.get("5m")
    setup = frames.get("15m")
    if trigger is None or setup is None or trigger.empty or setup.empty:
        result.detail = "Missing 5M/15M data"
        return result

    price = float(trigger["close"].iloc[-1])
    indicators = IndicatorSet.from_frame(setup)
    atr = indicators.last("atr14")
    ema21 = indicators.last("ema21")
    if not atr or atr <= 0 or ema21 is None:
        result.detail = "ATR/EMA unavailable"
        return result

    result.distance_to_entry_atr = round(abs(price - plan.entry) / atr, 3)
    result.extension_atr = round(abs(price - ema21) / atr, 3)

    pa5 = analyze_pa(frame_to_candles(trigger))
    if plan.direction == LONG and pa5.swing_lows:
        start = min(s.price for s in pa5.swing_lows[-5:])
        span = plan.tp1 - start
        consumed = (price - start) / span if span > 0 else 0.0
    elif pa5.swing_highs:
        start = max(s.price for s in pa5.swing_highs[-5:])
        span = start - plan.tp1
        consumed = (start - price) / span if span > 0 else 0.0
    else:
        consumed = 0.0
    result.impulse_consumed_pct = round(max(0.0, min(1.0, consumed)) * 100, 1)

    levels = pa5.supports if plan.direction == LONG else pa5.resistances
    nearest = min((abs(price - l.price) / atr for l in levels), default=99.0)
    result.mid_range = nearest > 1.0

    wrong_side = (price >= plan.tp1) if plan.direction == LONG else (price <= plan.tp1)
    stopped = (price <= plan.stop_loss) if plan.direction == LONG else (price >= plan.stop_loss)
    if stopped or wrong_side:
        result.location = EntryLocation.ENTRY_INVALIDATED
    elif result.impulse_consumed_pct > 60 or result.extension_atr > 2.5:
        result.location = EntryLocation.LATE_ENTRY
    elif result.distance_to_entry_atr > 0.8:
        result.location = EntryLocation.EARLY_ENTRY
    elif result.mid_range:
        result.location = EntryLocation.WAIT_FOR_RETEST
    else:
        result.location = EntryLocation.GOOD_ENTRY_ZONE
    result.prefer_retest = result.location in {EntryLocation.WAIT_FOR_RETEST, EntryLocation.EARLY_ENTRY}

    penalty = 0.0
    if result.location == EntryLocation.LATE_ENTRY:
        penalty += 4
    elif result.location == EntryLocation.EARLY_ENTRY:
        penalty += 3
    elif result.location == EntryLocation.WAIT_FOR_RETEST:
        penalty += 2
    elif result.location == EntryLocation.ENTRY_INVALIDATED:
        penalty = 10
    if result.risk_reward < min_risk_reward:
        penalty += 3
    if result.stop_atr_multiple > 3.0 or result.stop_atr_multiple < 0.5:
        penalty += 2
    if result.extension_atr > 3.0:
        penalty += 2
    result.score = round(max(0.0, 10.0 - penalty), 2)
    result.detail = (
        f"price={price:.8f}, entry={plan.entry:.8f}, dist={result.distance_to_entry_atr:.2f} ATR, "
        f"extension={result.extension_atr:.2f} ATR, impulse={result.impulse_consumed_pct:.1f}%, "
        f"RR={result.risk_reward:.2f}"
    )
    return result

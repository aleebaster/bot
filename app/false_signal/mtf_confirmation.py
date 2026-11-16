"""Multi-timeframe agreement with explicit countertrend/reversal handling."""

from __future__ import annotations

import pandas as pd

from app.constants import LONG
from app.false_signal.models import MTFAlignment, MTFConfirmationResult
from app.market_data.models import frame_to_candles
from app.price_action.structure import analyze as analyze_pa
from app.trend_analysis.analyzer import analyze_trend

BULL, BEAR, RANGE = "BULLISH", "BEARISH", "RANGING"

_SCORES = {
    MTFAlignment.FULL: 20.0,
    MTFAlignment.PARTIAL: 14.0,
    MTFAlignment.REVERSAL: 10.0,
    MTFAlignment.COUNTERTREND: 6.0,
    MTFAlignment.CONFLICT: 3.0,
}


def confirm_mtf(frames: dict[str, pd.DataFrame], direction: str) -> MTFConfirmationResult:
    result = MTFConfirmationResult()
    wanted = BULL if direction == LONG else BEAR
    opposite = BEAR if direction == LONG else BULL

    directions: dict[str, str] = {}
    for timeframe, frame in frames.items():
        if frame is not None and not frame.empty:
            directions[timeframe] = analyze_trend(frame, timeframe).direction
    result.directions = directions

    daily, four_hour = directions.get("1d", RANGE), directions.get("4h", RANGE)
    one_hour, fifteen, five = directions.get("1h", RANGE), directions.get("15m", RANGE), directions.get("5m", RANGE)

    reversal = False
    frame_4h = frames.get("4h")
    if frame_4h is not None and not frame_4h.empty:
        pa = analyze_pa(frame_to_candles(frame_4h))
        reversal = any(e.kind == "CHoCH" and e.direction == wanted for e in pa.events[-3:])

    if daily == opposite and four_hour == wanted:
        result.alignment = MTFAlignment.CONFLICT
    elif four_hour == wanted and one_hour == wanted and fifteen == wanted and five != opposite:
        result.alignment = MTFAlignment.FULL
    elif four_hour == wanted and one_hour != opposite:
        result.alignment = MTFAlignment.PARTIAL
    elif reversal:
        result.alignment = MTFAlignment.REVERSAL
    elif four_hour == opposite:
        result.alignment = MTFAlignment.COUNTERTREND
    else:
        result.alignment = MTFAlignment.PARTIAL

    result.countertrend = result.alignment in {MTFAlignment.COUNTERTREND, MTFAlignment.CONFLICT}
    result.score = _SCORES[result.alignment]
    result.detail = (
        f"1D={daily}, 4H={four_hour}, 1H={one_hour}, 15M={fifteen}, 5M={five}, "
        f"4H_CHoCH={reversal}"
    )
    return result

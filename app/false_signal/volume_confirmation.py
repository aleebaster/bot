"""Volume participation analysis: real participation vs move without support."""

from __future__ import annotations

import pandas as pd

from app.candle_patterns.detector import metrics
from app.constants import LONG
from app.false_signal.false_breakout import FalseBreakoutResult
from app.false_signal.models import VolumeConfirmationResult
from app.indicators.technical import sma


def confirm_volume(
    frame: pd.DataFrame,
    direction: str,
    breakout: FalseBreakoutResult,
) -> VolumeConfirmationResult:
    result = VolumeConfirmationResult()
    if len(frame) < 21:
        result.detail = "Insufficient volume history"
        return result

    volume = frame["volume"].astype(float)
    average = sma(volume, 20)
    rv = float(volume.iloc[-1]) / float(average.iloc[-1]) if average.iloc[-1] > 0 else 0.0
    prior_avg = float(average.iloc[-2]) if len(average) > 1 and average.iloc[-2] > 0 else 0.0
    prior_rv = float(volume.iloc[-2]) / prior_avg if prior_avg else 0.0
    result.relative_volume = round(rv, 3)
    result.spike = rv >= 1.5
    result.expansion = rv > prior_rv and rv >= 1.0
    result.breakout_volume = breakout.volume_confirmed
    result.weak_participation = rv < 1.0

    closes = frame["close"].astype(float)
    if len(closes) >= 4:
        price_up = closes.iloc[-1] > closes.iloc[-4]
        volume_down = volume.iloc[-1] < volume.iloc[-4]
        result.divergence = (direction == LONG and price_up and volume_down) or (
            direction != LONG and not price_up and volume_down
        )

    last = frame_to_last_candle(frame)
    if last is not None:
        m = metrics(last)
        result.rejection_volume = bool(rv >= 1.5 and max(m.upper_wick, m.lower_wick) >= 1.5 * max(m.body, 1e-12))

    score = 0.0
    if rv >= 1.5:
        score += 4
    elif rv >= 1.2:
        score += 3
    elif rv >= 1.0:
        score += 2
    if result.expansion:
        score += 2
    if result.breakout_volume:
        score += 2
    if not result.divergence:
        score += 1
    if result.weak_participation:
        score = min(score, 2.0)
    result.score = round(min(10.0, score), 2)
    result.detail = (
        f"RV={rv:.2f}, prior RV={prior_rv:.2f}, spike={result.spike}, expansion={result.expansion}, "
        f"breakout_volume={result.breakout_volume}, divergence={result.divergence}"
    )
    return result


def frame_to_last_candle(frame: pd.DataFrame):
    from app.market_data.models import frame_to_candles

    candles = frame_to_candles(frame.iloc[-1:])
    return candles[0] if candles else None

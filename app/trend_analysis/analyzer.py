"""Trend strength/direction analysis and multi-timeframe context aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.constants import CONFIRM_TIMEFRAME, CONTEXT_TIMEFRAME, TREND_TIMEFRAME
from app.indicators.technical import IndicatorSet
from app.market_data.models import frame_to_candles
from app.price_action.structure import BULLISH, BEARISH, RANGING, analyze as analyze_price_action

BULL_ALIGN = "BULLISH"
BEAR_ALIGN = "BEARISH"
MIXED = "MIXED"


@dataclass
class TrendResult:
    timeframe: str
    direction: str
    strength: float
    ema_alignment: str
    price_vs_vwap: str
    price_vs_ema200: str
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    adx_valid: bool

    @property
    def is_bullish(self) -> bool:
        return self.direction == BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == BEARISH


@dataclass
class MultiTimeframeContext:
    results: dict[str, TrendResult] = field(default_factory=dict)
    bias: str = RANGING
    aligned_long: bool = False
    aligned_short: bool = False
    trend_score: float = 0.0  # 0..20 contribution
    higher_trend: str = RANGING
    confirmation: str = RANGING


def analyze_trend(frame: pd.DataFrame, timeframe: str) -> TrendResult:
    """Combine EMA stacking, price vs VWAP/EMA200, ADX/DI and price structure."""
    indicators = IndicatorSet.from_frame(frame)
    close = float(frame["close"].iloc[-1])
    ema9 = indicators.last("ema9")
    ema21 = indicators.last("ema21")
    ema50 = indicators.last("ema50")
    ema200 = indicators.last("ema200")
    vwap = indicators.last("vwap")
    adx = indicators.last("adx")
    plus_di = indicators.last_plus_di()
    minus_di = indicators.last_minus_di()

    if None in (ema21, ema50, ema200, vwap):
        return TrendResult(timeframe, RANGING, 0.0, MIXED, "UNKNOWN", "UNKNOWN", adx, plus_di, minus_di, False)

    if close > ema21 > ema50 > ema200:
        ema_alignment = BULL_ALIGN
    elif close < ema21 < ema50 < ema200:
        ema_alignment = BEAR_ALIGN
    else:
        ema_alignment = MIXED

    price_vs_vwap = BULLISH if close > vwap else BEARISH
    price_vs_ema200 = BULLISH if close > ema200 else BEARISH

    adx_valid = adx is not None and adx >= 20.0
    di_bull = plus_di is not None and minus_di is not None and plus_di > minus_di
    di_bear = plus_di is not None and minus_di is not None and minus_di > plus_di

    pa = analyze_price_action(frame_to_candles(frame))
    votes = {
        BULLISH: 0,
        BEARISH: 0,
    }
    votes[BULLISH] += 2 if ema_alignment == BULL_ALIGN else 0
    votes[BEARISH] += 2 if ema_alignment == BEAR_ALIGN else 0
    votes[BULLISH] += 1 if price_vs_vwap == BULLISH else 0
    votes[BEARISH] += 1 if price_vs_vwap == BEARISH else 0
    votes[BULLISH] += 1 if price_vs_ema200 == BULLISH else 0
    votes[BEARISH] += 1 if price_vs_ema200 == BEARISH else 0
    votes[BULLISH] += 2 if pa.trend == BULLISH else 0
    votes[BEARISH] += 2 if pa.trend == BEARISH else 0
    if adx_valid:
        votes[BULLISH] += 2 if di_bull else 0
        votes[BEARISH] += 2 if di_bear else 0

    if votes[BULLISH] >= 5 and votes[BULLISH] > votes[BEARISH]:
        direction = BULLISH
    elif votes[BEARISH] >= 5 and votes[BEARISH] > votes[BULLISH]:
        direction = BEARISH
    else:
        direction = RANGING

    strength = min(1.0, (adx or 0.0) / 50.0)
    return TrendResult(
        timeframe=timeframe,
        direction=direction,
        strength=strength,
        ema_alignment=ema_alignment,
        price_vs_vwap=price_vs_vwap,
        price_vs_ema200=price_vs_ema200,
        adx=adx,
        plus_di=plus_di,
        minus_di=minus_di,
        adx_valid=adx_valid,
    )


class MultiTimeframeAnalyzer:
    """Aggregates trend results from higher to lower timeframes."""

    def analyze(self, frames: dict[str, pd.DataFrame]) -> MultiTimeframeContext:
        results = {tf: analyze_trend(frame, tf) for tf, frame in frames.items() if not frame.empty}
        context = MultiTimeframeContext(results=results)

        daily = results.get(CONTEXT_TIMEFRAME)
        four_hour = results.get(TREND_TIMEFRAME)
        one_hour = results.get(CONFIRM_TIMEFRAME)

        higher = [r for r in (daily, four_hour) if r is not None]
        bull_votes = sum(1 for r in higher if r.is_bullish)
        bear_votes = sum(1 for r in higher if r.is_bearish)
        context.higher_trend = BULLISH if bull_votes > bear_votes else BEARISH if bear_votes > bull_votes else RANGING
        context.confirmation = one_hour.direction if one_hour else RANGING

        context.aligned_long = (
            context.higher_trend == BULLISH
            and (one_hour is None or one_hour.direction != BEARISH)
        )
        context.aligned_short = (
            context.higher_trend == BEARISH
            and (one_hour is None or one_hour.direction != BULLISH)
        )

        weights = {CONTEXT_TIMEFRAME: 0.3, TREND_TIMEFRAME: 0.4, CONFIRM_TIMEFRAME: 0.3}
        score = 0.0
        total_weight = 0.0
        for tf, result in results.items():
            weight = weights.get(tf, 0.0)
            if weight == 0:
                continue
            direction_match = (
                1.0 if (context.higher_trend == BULLISH and result.is_bullish)
                or (context.higher_trend == BEARISH and result.is_bearish)
                else 0.0
            )
            score += weight * direction_match * (0.5 + 0.5 * result.strength)
            total_weight += weight
        context.trend_score = round(20.0 * (score / total_weight), 2) if total_weight else 0.0

        if context.aligned_long:
            context.bias = BULLISH
        elif context.aligned_short:
            context.bias = BEARISH
        else:
            context.bias = RANGING
        return context

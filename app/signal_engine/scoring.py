"""Transparent 0-100 scoring engine. Score is not a probability of profit."""

from __future__ import annotations

import pandas as pd

from app.candle_patterns.detector import BEARISH, BULLISH, PatternSignal
from app.constants import LONG, SHORT
from app.indicators.divergence import Divergence, RSIState
from app.price_action.structure import PriceActionResult
from app.signal_engine.models import ScoreBreakdown
from app.trend_analysis.analyzer import MultiTimeframeContext


def _volume_info(frame: pd.DataFrame) -> tuple[float, float]:
    if len(frame) < 21:
        return 0.0, 0.0
    volume = frame["volume"].astype(float)
    current = float(volume.iloc[-1])
    average = float(volume.iloc[-21:-1].mean())
    if average <= 0:
        return 0.0, current
    return current / average, current


def score_setup(
    context: MultiTimeframeContext,
    direction: str,
    rsi_state: RSIState,
    divergences: list[Divergence],
    setup_patterns: list[PatternSignal],
    trigger_patterns: list[PatternSignal],
    setup_pa: PriceActionResult,
    trigger_pa: PriceActionResult,
    setup_indicators,
    setup_frame: pd.DataFrame,
    stop_atr_multiple: float,
) -> tuple[ScoreBreakdown, list[str]]:
    """Score a candidate setup and produce human-readable reasons."""
    reasons: list[str] = []
    score = ScoreBreakdown()

    # --- Multi-timeframe trend (max 20) ------------------------------------
    aligned = context.aligned_long if direction == LONG else context.aligned_short
    score.multi_timeframe_trend = round(context.trend_score if aligned else context.trend_score * 0.4, 2)
    if aligned:
        reasons.append(f"Multi-timeframe trend aligned ({context.higher_trend})")
    else:
        reasons.append("Multi-timeframe trend not fully aligned")

    # --- RSI (max 15) -------------------------------------------------------
    value = rsi_state.value
    if value is not None:
        if direction == LONG:
            if value > 50:
                score.rsi += 6
                reasons.append(f"RSI 14 above 50 ({value:.1f})")
            if rsi_state.momentum_up:
                score.rsi += 3
            if rsi_state.exit_oversold:
                score.rsi += 2
                reasons.append("RSI exited oversold zone")
            if rsi_state.overbought:
                score.rsi -= 3
        else:
            if value < 50:
                score.rsi += 6
                reasons.append(f"RSI 14 below 50 ({value:.1f})")
            if not rsi_state.momentum_up:
                score.rsi += 3
            if rsi_state.exit_overbought:
                score.rsi += 2
                reasons.append("RSI exited overbought zone")
            if rsi_state.oversold:
                score.rsi -= 3
    favorable = {"bullish", "hidden_bullish"} if direction == LONG else {"bearish", "hidden_bearish"}
    for div in divergences:
        if div.kind in favorable:
            score.rsi += min(4, 2 + 2 * div.strength)
            reasons.append(f"{div.kind.replace('_', ' ').title()} divergence on {div.timeframe}")
            break
    score.rsi = round(max(0.0, min(15.0, score.rsi)), 2)

    # --- Candlestick (max 15) ----------------------------------------------
    wanted = BULLISH if direction == LONG else BEARISH
    trigger_pattern = next((p for p in trigger_patterns if p.direction == wanted), None)
    setup_pattern = next((p for p in setup_patterns if p.direction == wanted), None)
    for pattern in (setup_pattern, trigger_pattern):
        if pattern:
            score.candlestick += pattern.strength * 7
            if pattern.context_confirmed:
                score.candlestick += 1
            reasons.append(f"{pattern.name} ({pattern.direction.lower()})")
    score.candlestick = round(min(15.0, score.candlestick), 2)

    # --- Market structure (max 15) -----------------------------------------
    for pa in (setup_pa, trigger_pa):
        if (direction == LONG and pa.trend == BULLISH) or (direction == SHORT and pa.trend == BEARISH):
            score.market_structure += 5
        for event in pa.events[-3:]:
            if event.direction == wanted:
                score.market_structure += 3 if event.kind == "CHoCH" else 2
        if pa.sweep and pa.sweep.direction == wanted:
            score.market_structure += 3
            reasons.append(f"Liquidity sweep on {wanted.lower()} side")
        if pa.retest:
            score.market_structure += 2
            reasons.append("Breakout retest")
    score.market_structure = round(min(15.0, score.market_structure), 2)

    # --- Support / resistance (max 10) ------------------------------------
    last_close = float(setup_frame["close"].iloc[-1])
    levels = setup_pa.supports if direction == LONG else setup_pa.resistances
    if levels:
        nearest = levels[0]
        distance_pct = abs(last_close - nearest.price) / max(last_close, 1e-9)
        if distance_pct <= 0.015:
            score.support_resistance += 6
            reasons.append(f"Near {nearest.kind} at {nearest.price:.8f}")
        score.support_resistance += round(nearest.strength * 4, 2)

    # --- Volume (max 10) ----------------------------------------------------
    relative_volume, _ = _volume_info(setup_frame)
    if relative_volume >= 1.5:
        score.volume += 6
    elif relative_volume >= 1.2:
        score.volume += 4
    elif relative_volume >= 1.0:
        score.volume += 2
    if relative_volume >= 1.5 and (setup_pa.breakout_confirmed or trigger_pa.breakout_confirmed):
        score.volume += 4
        reasons.append("Volume confirms breakout")
    elif relative_volume >= 1.2:
        score.volume += 2
    score.volume = round(min(10.0, score.volume), 2)

    # --- EMA / VWAP (max 10) -----------------------------------------------
    close = last_close
    vwap = setup_indicators.last("vwap")
    ema200 = setup_indicators.last("ema200")
    ema_alignment = context.results.get("15m")
    if vwap is not None:
        if (direction == LONG and close > vwap) or (direction == SHORT and close < vwap):
            score.ema_vwap += 4
            reasons.append(f"Price {'above' if direction == LONG else 'below'} VWAP")
    if ema_alignment and (
        (direction == LONG and ema_alignment.ema_alignment == BULLISH)
        or (direction == SHORT and ema_alignment.ema_alignment == BEARISH)
    ):
        score.ema_vwap += 4
        reasons.append("EMA stack aligned")
    if ema200 is not None:
        if (direction == LONG and close > ema200) or (direction == SHORT and close < ema200):
            score.ema_vwap += 2
    score.ema_vwap = round(min(10.0, score.ema_vwap), 2)

    # --- Volatility / entry quality (max 5) --------------------------------
    if 0.8 <= stop_atr_multiple <= 2.5:
        score.volatility_entry = 5.0
    elif 0.5 <= stop_atr_multiple <= 3.0:
        score.volatility_entry = 3.0
    else:
        score.volatility_entry = 1.0

    # Hard penalty: DO NOT buy an already-extended impulse.
    ema21 = setup_indicators.last("ema21")
    atr = setup_indicators.last("atr14")
    if ema21 is not None and atr is not None and atr > 0:
        extension = abs(close - ema21) / atr
        if extension > 3.0:
            score.volatility_entry = 0.0
            score.market_structure = max(0.0, score.market_structure - 5)
            reasons.append("Setup extended >3 ATR from EMA21 - penalised")

    return score, reasons

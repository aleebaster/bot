"""Multi-timeframe signal engine. Emits signals only after closed-bar confirmation."""

from __future__ import annotations

import logging
import time

import pandas as pd

from app.candle_patterns.detector import BEARISH, BULLISH, detect_patterns
from app.config import Settings
from app.constants import CONFIRM_TIMEFRAME, LONG, SETUP_TIMEFRAME, SHORT, TRIGGER_TIMEFRAME
from app.indicators.divergence import analyze_rsi, detect_divergences
from app.indicators.technical import IndicatorSet
from app.market_data.models import frame_to_candles, timeframe_to_ms
from app.price_action.structure import analyze as analyze_price_action
from app.risk_management.manager import RiskManager
from app.risk_management.position import InvalidTradePlan
from app.signal_engine.models import EngineResult, Signal, make_signal_id
from app.signal_engine.scoring import score_setup
from app.trend_analysis.analyzer import MultiTimeframeAnalyzer

logger = logging.getLogger(__name__)

REQUIRED_TIMEFRAMES = ("4h", CONFIRM_TIMEFRAME, SETUP_TIMEFRAME, TRIGGER_TIMEFRAME)
MIN_BARS = {SETUP_TIMEFRAME: 50, TRIGGER_TIMEFRAME: 40, CONFIRM_TIMEFRAME: 50, "4h": 60}


def _relative_volume(frame: pd.DataFrame) -> float:
    if len(frame) < 21:
        return 0.0
    avg = float(frame["volume"].astype(float).iloc[-21:-1].mean())
    return float(frame["volume"].iloc[-1]) / avg if avg > 0 else 0.0


def _no_trade(reason: str, **diagnostics: object) -> EngineResult:
    return EngineResult(signal=None, reason=reason, diagnostics=diagnostics)


class SignalEngine:
    """Orchestrates analysis across timeframes and applies hard filters.

    The guiding principle is quality over quantity: when any condition is
    missing the engine returns NO TRADE rather than a speculative signal.
    """

    def __init__(self, settings: Settings, risk_manager: RiskManager, analyzer: MultiTimeframeAnalyzer | None = None) -> None:
        self.settings = settings
        self.risk_manager = risk_manager
        self.analyzer = analyzer or MultiTimeframeAnalyzer()

    def generate(
        self, symbol: str, frames: dict[str, pd.DataFrame], meta: dict | None = None
    ) -> EngineResult:
        meta = meta or {}
        now_ms = int(meta.get("now_ms") or time.time() * 1000)

        # 1) Data quality: freshness and minimum history.
        for timeframe, frame in frames.items():
            if frame.empty:
                continue
            last_ts = int(frame["timestamp"].iloc[-1])
            age_seconds = (now_ms - last_ts) / 1000.0
            # A closed 1D bar is naturally up to 24h old. Applying a flat
            # 180s quote-age limit to every timeframe makes higher timeframes
            # permanently "stale" and blocks every signal. The tolerance must
            # scale with the bar duration while still rejecting a dead feed.
            allowed_age = max(
                self.settings.max_quote_age_seconds,
                2.0 * timeframe_to_ms(timeframe) / 1000.0 + 60.0,
            )
            if age_seconds > allowed_age:
                return _no_trade(
                    f"Stale data on {timeframe} ({age_seconds:.0f}s old, limit {allowed_age:.0f}s)",
                    age=age_seconds,
                )
            if bool(frame["closed"].iloc[-1]) is False:
                return _no_trade(f"Unconfirmed candle on {timeframe}")

        for timeframe in REQUIRED_TIMEFRAMES:
            frame = frames.get(timeframe)
            if frame is None or len(frame) < MIN_BARS.get(timeframe, 30):
                return _no_trade(f"Insufficient history on {timeframe}")

        # 2) Higher-timeframe direction.
        context = self.analyzer.analyze(frames)
        if context.aligned_long:
            direction = LONG
        elif context.aligned_short:
            direction = SHORT
        else:
            return _no_trade(f"No multi-timeframe alignment (bias={context.bias})", bias=context.bias)

        setup_frame = frames[SETUP_TIMEFRAME]
        trigger_frame = frames[TRIGGER_TIMEFRAME]
        setup_ind = IndicatorSet.from_frame(setup_frame)
        trigger_ind = IndicatorSet.from_frame(trigger_frame)
        setup_candles = frame_to_candles(setup_frame)
        trigger_candles = frame_to_candles(trigger_frame)

        setup_pa = analyze_price_action(setup_candles)
        trigger_pa = analyze_price_action(trigger_candles)
        confirm_pa = analyze_price_action(frame_to_candles(frames[CONFIRM_TIMEFRAME]))
        rsi_state = analyze_rsi(setup_frame, SETUP_TIMEFRAME)
        trigger_rsi = analyze_rsi(trigger_frame, TRIGGER_TIMEFRAME)
        divergences = [
            *detect_divergences(setup_frame, SETUP_TIMEFRAME, 14),
            *detect_divergences(trigger_frame, TRIGGER_TIMEFRAME, 14),
        ]
        setup_patterns = detect_patterns(setup_candles)
        trigger_patterns = detect_patterns(trigger_candles)
        wanted = BULLISH if direction == LONG else BEARISH

        favorable_div = any(
            d.kind in ({"bullish", "hidden_bullish"} if direction == LONG else {"bearish", "hidden_bearish"})
            for d in divergences
        )

        # 3) 15M setup conditions.
        setup_rsi_ok = (
            (rsi_state.value is not None and ((direction == LONG and rsi_state.value > 50) or (direction == SHORT and rsi_state.value < 50)))
            or favorable_div
        )
        if not setup_rsi_ok:
            return _no_trade("15M RSI does not confirm direction")
        setup_pa_ok = (
            (direction == LONG and setup_pa.trend == BULLISH)
            or (direction == SHORT and setup_pa.trend == BEARISH)
            or any(e.direction == wanted for e in setup_pa.events[-3:])
            or (setup_pa.sweep is not None and setup_pa.sweep.direction == wanted)
        )
        if not setup_pa_ok:
            return _no_trade("15M market structure does not confirm setup")

        # 4) 5M trigger conditions (last CLOSED bar).
        trigger_close = float(trigger_frame["close"].iloc[-1])
        ema21_5 = trigger_ind.last("ema21")
        vwap_5 = trigger_ind.last("vwap")
        if ema21_5 is None or vwap_5 is None:
            return _no_trade("5M indicators not ready")
        ema_ok = (trigger_close > ema21_5 and trigger_close > vwap_5) if direction == LONG else (
            trigger_close < ema21_5 and trigger_close < vwap_5
        )
        if not ema_ok:
            return _no_trade("5M EMA/VWAP trigger not met")

        trigger_rsi_ok = (
            (trigger_rsi.value is not None and ((direction == LONG and trigger_rsi.value > 50) or (direction == SHORT and trigger_rsi.value < 50)))
            or favorable_div
            or (direction == LONG and trigger_rsi.crossed_above_50)
            or (direction == SHORT and trigger_rsi.crossed_below_50)
        )
        if not trigger_rsi_ok:
            return _no_trade("5M RSI trigger not met")

        trigger_pattern = next((p for p in trigger_patterns if p.direction == wanted), None)
        if trigger_pattern is None:
            return _no_trade("No 5M candlestick trigger")
        trigger_pa_ok = (
            (direction == LONG and trigger_pa.trend == BULLISH)
            or (direction == SHORT and trigger_pa.trend == BEARISH)
            or any(e.direction == wanted for e in trigger_pa.events[-3:])
            or (trigger_pa.sweep is not None and trigger_pa.sweep.direction == wanted)
        )
        if not trigger_pa_ok:
            return _no_trade("5M structure trigger not met")

        rv_5 = _relative_volume(trigger_frame)
        rv_15 = _relative_volume(setup_frame)
        if rv_5 < 1.0 or rv_15 < 0.8:
            return _no_trade(f"Insufficient volume (5M={rv_5:.2f}, 15M={rv_15:.2f})", rv_5=rv_5, rv_15=rv_15)

        # 5) Entry / stop / targets.
        atr15 = setup_ind.last("atr14")
        atr5 = trigger_ind.last("atr14")
        if not atr15 or not atr5 or atr15 <= 0 or atr5 <= 0:
            return _no_trade("ATR unavailable")

        entry_low = trigger_close - 0.15 * atr5
        entry_high = trigger_close + 0.15 * atr5
        entry = trigger_close

        if direction == LONG:
            swings = [s.price for s in trigger_pa.swing_lows[-3:] if s.price < entry]
            swings += [s.price for s in setup_pa.swing_lows[-3:] if s.price < entry]
            raw_stop = max(swings) - 0.1 * atr5 if swings else entry - 1.5 * atr15
            nearest_stop, furthest_stop = entry - 0.8 * atr15, entry - 2.5 * atr15
            stop_loss = max(furthest_stop, min(raw_stop, nearest_stop))
        else:
            swings = [s.price for s in trigger_pa.swing_highs[-3:] if s.price > entry]
            swings += [s.price for s in setup_pa.swing_highs[-3:] if s.price > entry]
            raw_stop = min(swings) + 0.1 * atr5 if swings else entry + 1.5 * atr15
            nearest_stop, furthest_stop = entry + 0.8 * atr15, entry + 2.5 * atr15
            stop_loss = min(furthest_stop, max(raw_stop, nearest_stop))

        if direction == LONG:
            structural_targets = [l.price for l in setup_pa.resistances] + [l.price for l in confirm_pa.resistances]
        else:
            structural_targets = [l.price for l in setup_pa.supports] + [l.price for l in confirm_pa.supports]

        try:
            plan = self.risk_manager.plan(
                symbol=symbol,
                direction=direction,
                entry_low=entry_low,
                entry_high=entry_high,
                stop_loss=stop_loss,
                structural_targets=structural_targets,
                atr=atr15,
                holding_bars_1h=8,
            )
        except InvalidTradePlan as exc:
            return _no_trade(f"Trade plan rejected: {exc}")

        # 6) Score and final threshold.
        breakdown, reasons = score_setup(
            context=context,
            direction=direction,
            rsi_state=rsi_state,
            divergences=divergences,
            setup_patterns=setup_patterns,
            trigger_patterns=trigger_patterns,
            setup_pa=setup_pa,
            trigger_pa=trigger_pa,
            setup_indicators=setup_ind,
            setup_frame=setup_frame,
            stop_atr_multiple=plan.stop_atr_multiple,
        )
        if breakdown.total < self.settings.min_signal_score:
            return _no_trade(
                f"Score {breakdown.total} below threshold {self.settings.min_signal_score}",
                score=breakdown.total,
                breakdown=breakdown.as_dict(),
            )
        if trigger_pa.false_breakout:
            return _no_trade("False breakout detected on trigger timeframe")

        market_context = (
            f"{context.higher_trend} daily/4H context | {context.confirmation} 1H | "
            f"{setup_pa.trend} 15M | {trigger_pa.trend} 5M"
        )
        invalidation = (
            f"15M close below {plan.stop_loss:.8f} (structural invalidation)"
            if direction == LONG
            else f"15M close above {plan.stop_loss:.8f} (structural invalidation)"
        )
        if direction == LONG:
            reasons.append(f"Stop below swing low / {plan.stop_atr_multiple:.2f}x ATR")
        else:
            reasons.append(f"Stop above swing high / {plan.stop_atr_multiple:.2f}x ATR")
        reasons.extend(plan.target_reasons)

        signal = Signal(
            symbol=symbol,
            direction=direction,
            timestamp=int(trigger_frame["timestamp"].iloc[-1]),
            signal_id=make_signal_id(symbol, direction, int(trigger_frame["timestamp"].iloc[-1]), plan.entry),
            timeframes=[TRIGGER_TIMEFRAME, SETUP_TIMEFRAME, CONFIRM_TIMEFRAME, "4h"],
            setup_timeframe=SETUP_TIMEFRAME,
            trigger_timeframe=TRIGGER_TIMEFRAME,
            plan=plan,
            score=breakdown.total,
            score_breakdown=breakdown,
            rsi14=rsi_state.value,
            trend=context.bias,
            atr=atr15,
            market_context=market_context,
            reasons=reasons,
            invalidation=invalidation,
            funding_rate=meta.get("funding_rate"),
            open_interest=meta.get("open_interest"),
            expiration=now_ms + 4 * 60 * 60 * 1000,
        )
        return EngineResult(
            signal=signal,
            reason="All conditions met",
            score=breakdown.total,
            category=breakdown.category,
            diagnostics={"score": breakdown.as_dict(), "relative_volume_5m": rv_5},
        )

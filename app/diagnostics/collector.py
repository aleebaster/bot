"""Read-only diagnostic collector.

Mirrors the exact checks of :class:`app.signal_engine.engine.SignalEngine`,
but evaluates EVERY check (not just the first failure) and computes scores for
both LONG and SHORT. It never changes thresholds, weights or strategy rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
from app.signal_engine.engine import MIN_BARS, REQUIRED_TIMEFRAMES, SignalEngine, _relative_volume
from app.signal_engine.models import ScoreBreakdown
from app.signal_engine.scoring import score_setup
from app.trend_analysis.analyzer import MultiTimeframeAnalyzer, TrendResult, analyze_trend


@dataclass
class TimeframeStats:
    timeframe: str
    bars: int
    last_bar_ts: int
    last_close: float
    bar_closed: bool
    rsi7: float | None
    rsi14: float | None
    rsi21: float | None
    ema9: float | None
    ema21: float | None
    ema50: float | None
    ema200: float | None
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    atr14: float | None
    vwap: float | None
    volume: float
    volume_sma20: float | None
    relative_volume: float
    trend_direction: str
    trend_strength: float
    ema_alignment: str
    price_vs_vwap: str
    price_vs_ema200: str
    structure_trend: str
    patterns: list[str] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)


@dataclass
class FilterCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class DirectionScore:
    direction: str
    total: float
    category: str
    components: dict[str, float]
    reasons: list[str]


@dataclass
class SymbolDiagnosis:
    symbol: str
    stats: dict[str, TimeframeStats]
    bias: str
    higher_trend: str
    confirmation: str
    aligned_long: bool
    aligned_short: bool
    trend_score: float
    checks: list[FilterCheck]
    scores: dict[str, DirectionScore]
    engine_reason: str
    engine_score: float
    crosscheck_ok: bool
    plan_notes: dict[str, str] = field(default_factory=dict)

    @property
    def first_failed(self) -> FilterCheck | None:
        return next((c for c in self.checks if not c.passed), None)


def _fmt(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _tf_stats(frame: pd.DataFrame, timeframe: str) -> TimeframeStats:
    indicators = IndicatorSet.from_frame(frame)
    candle_frame = frame_to_candles(frame)
    pa = analyze_price_action(candle_frame)
    try:
        divergences = [d.kind for d in detect_divergences(frame, timeframe, 14)]
    except Exception:
        divergences = []
    return TimeframeStats(
        timeframe=timeframe,
        bars=len(frame),
        last_bar_ts=int(frame["timestamp"].iloc[-1]),
        last_close=float(frame["close"].iloc[-1]),
        bar_closed=bool(frame["closed"].iloc[-1]),
        rsi7=indicators.last("rsi7"),
        rsi14=indicators.last("rsi14"),
        rsi21=indicators.last("rsi21"),
        ema9=indicators.last("ema9"),
        ema21=indicators.last("ema21"),
        ema50=indicators.last("ema50"),
        ema200=indicators.last("ema200"),
        adx=indicators.last("adx"),
        plus_di=indicators.last_plus_di(),
        minus_di=indicators.last_minus_di(),
        atr14=indicators.last("atr14"),
        vwap=indicators.last("vwap"),
        volume=float(frame["volume"].iloc[-1]),
        volume_sma20=indicators.last("volume_sma20"),
        relative_volume=_relative_volume(frame),
        trend_direction=analyze_trend(frame, timeframe).direction,
        trend_strength=analyze_trend(frame, timeframe).strength,
        ema_alignment=analyze_trend(frame, timeframe).ema_alignment,
        price_vs_vwap=analyze_trend(frame, timeframe).price_vs_vwap,
        price_vs_ema200=analyze_trend(frame, timeframe).price_vs_ema200,
        structure_trend=pa.trend,
        patterns=[p.name for p in detect_patterns(candle_frame)],
        divergences=divergences,
    )


def _try_plan(
    direction: str,
    settings: Settings,
    risk: RiskManager,
    trigger_stats: TimeframeStats,
    setup_stats: TimeframeStats,
    setup_pa,
    trigger_pa,
    confirm_pa,
) -> tuple[str, bool, float, str]:
    """Attempt a trade plan for either direction. Returns (note, ok, atr_mult, stop)."""
    atr5, atr15 = trigger_stats.atr14, setup_stats.atr14
    if not atr5 or not atr15:
        return "ATR unavailable", False, 0.0, ""
    entry = trigger_stats.last_close
    try:
        if direction == LONG:
            swings = [s.price for s in trigger_pa.swing_lows[-3:] if s.price < entry]
            swings += [s.price for s in setup_pa.swing_lows[-3:] if s.price < entry]
            raw = max(swings) - 0.1 * atr5 if swings else entry - 1.5 * atr15
            stop = max(entry - 2.5 * atr15, min(raw, entry - 0.8 * atr15))
            targets = [l.price for l in setup_pa.resistances] + [l.price for l in confirm_pa.resistances]
        else:
            swings = [s.price for s in trigger_pa.swing_highs[-3:] if s.price > entry]
            swings += [s.price for s in setup_pa.swing_highs[-3:] if s.price > entry]
            raw = min(swings) + 0.1 * atr5 if swings else entry + 1.5 * atr15
            stop = min(entry + 2.5 * atr15, max(raw, entry + 0.8 * atr15))
            targets = [l.price for l in setup_pa.supports] + [l.price for l in confirm_pa.supports]
        plan = risk.plan(
            symbol="", direction=direction,
            entry_low=entry - 0.15 * atr5, entry_high=entry + 0.15 * atr5,
            stop_loss=stop, structural_targets=targets, atr=atr15,
        )
        return (
            f"OK: SL={plan.stop_loss:.8f}, RR=1:{plan.risk_reward:.2f}, "
            f"stop={plan.stop_atr_multiple:.2f}x ATR, size={plan.position_size}, cost={plan.estimated_cost:.4f}",
            True, plan.stop_atr_multiple, f"{plan.stop_loss:.8f}",
        )
    except InvalidTradePlan as exc:
        return f"REJECTED: {exc}", False, 0.0, ""


def diagnose_symbol(
    symbol: str,
    frames: dict[str, pd.DataFrame],
    settings: Settings,
    risk: RiskManager,
    now_ms: int,
) -> SymbolDiagnosis:
    """Collect full diagnostics for one symbol without changing any decision."""
    analyzer = MultiTimeframeAnalyzer()
    context = analyzer.analyze(frames)
    stats = {tf: _tf_stats(frame, tf) for tf, frame in frames.items() if not frame.empty}
    checks: list[FilterCheck] = []

    # --- data quality (mirrors engine order) ---
    for timeframe, frame in frames.items():
        if frame.empty:
            continue
        age = (now_ms - int(frame["timestamp"].iloc[-1])) / 1000.0
        allowed_age = max(settings.max_quote_age_seconds, 2.0 * timeframe_to_ms(timeframe) / 1000.0 + 60.0)
        checks.append(FilterCheck(
            f"freshness:{timeframe}", age <= allowed_age,
            f"last closed bar age = {age:.0f}s (limit {allowed_age:.0f}s)",
        ))
        checks.append(FilterCheck(
            f"closed_bar:{timeframe}", bool(frame["closed"].iloc[-1]),
            f"last bar closed = {bool(frame['closed'].iloc[-1])}",
        ))
    for timeframe in REQUIRED_TIMEFRAMES:
        frame = frames.get(timeframe)
        count = 0 if frame is None else len(frame)
        checks.append(FilterCheck(
            f"history:{timeframe}", count >= MIN_BARS.get(timeframe, 30),
            f"{count} bars (min {MIN_BARS.get(timeframe, 30)})",
        ))

    checks.append(FilterCheck(
        "mtf_alignment", context.aligned_long or context.aligned_short,
        f"bias={context.bias}, higher={context.higher_trend}, 1H={context.confirmation}",
    ))

    setup_frame, trigger_frame = frames[SETUP_TIMEFRAME], frames[TRIGGER_TIMEFRAME]
    setup_ind = IndicatorSet.from_frame(setup_frame)
    trigger_ind = IndicatorSet.from_frame(trigger_frame)
    setup_pa = analyze_price_action(frame_to_candles(setup_frame))
    trigger_pa = analyze_price_action(frame_to_candles(trigger_frame))
    confirm_pa = analyze_price_action(frame_to_candles(frames[CONFIRM_TIMEFRAME]))
    rsi_state = analyze_rsi(setup_frame, SETUP_TIMEFRAME)
    trigger_rsi = analyze_rsi(trigger_frame, TRIGGER_TIMEFRAME)
    divergences = [
        *detect_divergences(setup_frame, SETUP_TIMEFRAME, 14),
        *detect_divergences(trigger_frame, TRIGGER_TIMEFRAME, 14),
    ]
    setup_patterns = detect_patterns(frame_to_candles(setup_frame))
    trigger_patterns = detect_patterns(frame_to_candles(trigger_frame))

    direction = LONG if context.aligned_long else SHORT if context.aligned_short else ""
    plan_notes: dict[str, str] = {}
    score_objects: dict[str, DirectionScore] = {}

    for candidate in (LONG, SHORT):
        wanted = BULLISH if candidate == LONG else BEARISH
        favorable = any(
            d.kind in ({"bullish", "hidden_bullish"} if candidate == LONG else {"bearish", "hidden_bearish"})
            for d in divergences
        )
        plan_note, plan_ok, atr_mult, _ = _try_plan(
            candidate, settings, risk, stats[TRIGGER_TIMEFRAME], stats[SETUP_TIMEFRAME],
            setup_pa, trigger_pa, confirm_pa,
        )
        plan_notes[candidate] = plan_note
        breakdown, reasons = score_setup(
            context=context, direction=candidate, rsi_state=rsi_state,
            divergences=divergences, setup_patterns=setup_patterns,
            trigger_patterns=trigger_patterns, setup_pa=setup_pa, trigger_pa=trigger_pa,
            setup_indicators=setup_ind, setup_frame=setup_frame,
            stop_atr_multiple=atr_mult if plan_ok else 1.5,
        )
        score_objects[candidate] = DirectionScore(
            direction=candidate, total=breakdown.total, category=breakdown.category,
            components=breakdown.as_dict(), reasons=reasons,
        )

    if direction:
        wanted = BULLISH if direction == LONG else BEARISH
        favorable = any(
            d.kind in ({"bullish", "hidden_bullish"} if direction == LONG else {"bearish", "hidden_bearish"})
            for d in divergences
        )
        setup_rsi_ok = (
            rsi_state.value is not None
            and ((direction == LONG and rsi_state.value > 50) or (direction == SHORT and rsi_state.value < 50))
        ) or favorable
        checks.append(FilterCheck("setup_rsi_15m", setup_rsi_ok,
            f"RSI14(15m)={_fmt(rsi_state.value, 2)}, favourable_divergence={favorable}"))
        setup_pa_ok = (
            (direction == LONG and setup_pa.trend == BULLISH)
            or (direction == SHORT and setup_pa.trend == BEARISH)
            or any(e.direction == wanted for e in setup_pa.events[-3:])
            or (setup_pa.sweep is not None and setup_pa.sweep.direction == wanted)
        )
        checks.append(FilterCheck("setup_structure_15m", setup_pa_ok,
            f"structure={setup_pa.trend}, events={[e.kind + ':' + e.direction for e in setup_pa.events[-3:]]}, sweep={setup_pa.sweep}"))

        trigger_close = float(trigger_frame["close"].iloc[-1])
        ema21_5, vwap_5 = trigger_ind.last("ema21"), trigger_ind.last("vwap")
        ema_ok = (trigger_close > ema21_5 and trigger_close > vwap_5) if direction == LONG else (
            trigger_close < ema21_5 and trigger_close < vwap_5
        )
        checks.append(FilterCheck("trigger_ema_vwap_5m", ema_ok,
            f"close={trigger_close:.8f}, EMA21={_fmt(ema21_5, 8)}, VWAP={_fmt(vwap_5, 8)}"))
        trigger_rsi_ok = (
            (trigger_rsi.value is not None and ((direction == LONG and trigger_rsi.value > 50) or (direction == SHORT and trigger_rsi.value < 50)))
            or favorable
            or (direction == LONG and trigger_rsi.crossed_above_50)
            or (direction == SHORT and trigger_rsi.crossed_below_50)
        )
        checks.append(FilterCheck("trigger_rsi_5m", trigger_rsi_ok,
            f"RSI14(5m)={_fmt(trigger_rsi.value, 2)}, cross50=({trigger_rsi.crossed_above_50},{trigger_rsi.crossed_below_50})"))
        trigger_pattern = next((p for p in trigger_patterns if p.direction == wanted), None)
        checks.append(FilterCheck("trigger_candle_5m", trigger_pattern is not None,
            f"patterns={[p.name + ':' + p.direction for p in trigger_patterns]}"))
        trigger_pa_ok = (
            (direction == LONG and trigger_pa.trend == BULLISH)
            or (direction == SHORT and trigger_pa.trend == BEARISH)
            or any(e.direction == wanted for e in trigger_pa.events[-3:])
            or (trigger_pa.sweep is not None and trigger_pa.sweep.direction == wanted)
        )
        checks.append(FilterCheck("trigger_structure_5m", trigger_pa_ok,
            f"structure={trigger_pa.trend}, events={[e.kind + ':' + e.direction for e in trigger_pa.events[-3:]]}"))

        rv_5, rv_15 = _relative_volume(trigger_frame), _relative_volume(setup_frame)
        checks.append(FilterCheck("volume", rv_5 >= 1.0 and rv_15 >= 0.8,
            f"RV(5m)={rv_5:.2f}, RV(15m)={rv_15:.2f}"))

        checks.append(FilterCheck("trade_plan", plan_notes[direction].startswith("OK"), plan_notes[direction]))

        score = score_objects[direction].total
        checks.append(FilterCheck("score_threshold", score >= settings.min_signal_score,
            f"score={score:.2f} vs threshold {settings.min_signal_score}"))
        checks.append(FilterCheck("false_breakout", not trigger_pa.false_breakout,
            f"false_breakout={trigger_pa.false_breakout}"))

    engine_result = SignalEngine(settings, risk, analyzer).generate(
        symbol, frames, {"now_ms": now_ms}
    )

    first_failed = next((c for c in checks if not c.passed), None)
    crosscheck = (engine_result.signal is None) and first_failed is not None

    return SymbolDiagnosis(
        symbol=symbol, stats=stats, bias=context.bias,
        higher_trend=context.higher_trend, confirmation=context.confirmation,
        aligned_long=context.aligned_long, aligned_short=context.aligned_short,
        trend_score=context.trend_score, checks=checks, scores=score_objects,
        engine_reason=engine_result.reason, engine_score=engine_result.score,
        crosscheck_ok=crosscheck, plan_notes=plan_notes,
    )

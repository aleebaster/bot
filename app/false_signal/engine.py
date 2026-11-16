"""False Signal Detection Engine — orchestrates all confirmation sub-engines."""

from __future__ import annotations

import logging
import time

import pandas as pd

from app.config import Settings
from app.constants import LONG, TRIGGER_TIMEFRAME
from app.false_signal.candle_confirmation import confirm_candle
from app.false_signal.entry_quality import analyze_entry_quality
from app.false_signal.false_breakout import detect_false_breakout
from app.false_signal.liquidity_trap import detect_liquidity_trap
from app.false_signal.models import (
    ConfirmationVerdict,
    EntryVerdict,
    Finding,
    MTFAlignment,
    RecheckResult,
)
from app.false_signal.mtf_confirmation import confirm_mtf
from app.false_signal.rsi_confirmation import confirm_rsi
from app.false_signal.scoring import (
    build_confirmation_score,
    build_false_signal_risk,
    decide_verdict,
    hard_rejection_checks,
)
from app.false_signal.volume_confirmation import confirm_volume
from app.indicators.technical import IndicatorSet
from app.market_data.models import frame_to_candles, freshness_limit_seconds
from app.price_action.structure import analyze as analyze_pa
from app.risk_management.position import TradePlan

logger = logging.getLogger(__name__)


def _relative_volume(frame: pd.DataFrame) -> float:
    """Same definition as the base engine, kept local to avoid import cycles."""
    if len(frame) < 21:
        return 0.0
    average = float(frame["volume"].astype(float).iloc[-21:-1].mean())
    return float(frame["volume"].iloc[-1]) / average if average > 0 else 0.0


def _reference_level(pa, direction: str, price: float) -> float | None:
    levels = pa.resistances if direction == LONG else pa.supports
    candidates = [l.price for l in levels if (l.price > price if direction == LONG else l.price < price)]
    if candidates:
        return min(candidates) if direction == LONG else max(candidates)
    swings = [s.price for s in (pa.swing_highs if direction == LONG else pa.swing_lows)]
    if not swings:
        return None
    return min(swings) if direction == LONG else max(swings)


def _price_action_score(pa5, pa15, direction: str) -> tuple[float, list[str]]:
    wanted = "BULLISH" if direction == LONG else "BEARISH"
    score = 0.0
    notes: list[str] = []
    for pa, label in ((pa15, "15M"), (pa5, "5M")):
        if pa.trend == wanted:
            score += 4
            notes.append(f"{label} structure {wanted.lower()}")
        if any(e.direction == wanted for e in pa.events[-3:]):
            score += 2
            notes.append(f"{label} structure break in direction")
        if pa.sweep and pa.sweep.direction == wanted:
            score += 2
            notes.append(f"{label} liquidity sweep in direction")
        if pa.retest:
            score += 1
            notes.append(f"{label} retest")
    return min(15.0, score), notes


class FalseSignalEngine:
    """Add-only quality gate. Does not change base strategy or score threshold."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        symbol: str,
        direction: str,
        frames: dict[str, pd.DataFrame],
        plan: TradePlan,
        now_ms: int | None = None,
    ) -> ConfirmationVerdict:
        now = now_ms or int(time.time() * 1000)
        trigger = frames.get(TRIGGER_TIMEFRAME)
        setup = frames.get("15m")
        if trigger is None or setup is None or trigger.empty or setup.empty:
            return self._empty_verdict("Missing 5M/15M data")

        rv5 = _relative_volume(trigger)
        rv15 = _relative_volume(setup)
        atr5 = IndicatorSet.from_frame(trigger).last("atr14") or 0.0
        pa5 = analyze_pa(frame_to_candles(trigger))
        pa15 = analyze_pa(frame_to_candles(setup))

        price = float(trigger["close"].iloc[-1])
        level = _reference_level(pa15, direction, price)
        breakout = detect_false_breakout(
            frame_to_candles(trigger), direction, level, atr5, rv5
        )
        trap = detect_liquidity_trap(
            frame_to_candles(trigger), direction, pa5, breakout, atr5, rv5
        )
        rsi = confirm_rsi(setup, direction, "15m")
        candle = confirm_candle(frame_to_candles(trigger), direction, pa5, rv5, atr5)
        volume = confirm_volume(trigger, direction, breakout)
        mtf = confirm_mtf(frames, direction)
        entry = analyze_entry_quality(plan, frames, self.settings.min_risk_reward)
        pa_score, pa_notes = _price_action_score(pa5, pa15, direction)
        volatility = 5.0 if 0.8 <= plan.stop_atr_multiple <= 2.5 else (3.0 if 0.5 <= plan.stop_atr_multiple <= 3.0 else 0.0)

        confirmation = build_confirmation_score(
            mtf, pa_score, rsi, candle, volume, breakout, entry, volatility
        )
        risk = build_false_signal_risk(
            breakout, trap, rsi, candle, volume, mtf, entry, self.settings.min_risk_reward
        )

        fresh = all(
            (now - int(f["timestamp"].iloc[-1])) / 1000.0
            <= freshness_limit_seconds(tf, self.settings.max_quote_age_seconds)
            for tf, f in frames.items()
            if f is not None and not f.empty
        )

        blocks = hard_rejection_checks(
            breakout, trap, mtf, candle, entry, fresh, self.settings.min_risk_reward
        )

        reasons_confirm: list[str] = []
        reasons_reject: list[str] = []
        if confirmation.multi_timeframe >= 14:
            reasons_confirm.append(f"Trend alignment: {mtf.alignment.value}")
        if rsi.score >= 8:
            reasons_confirm.append("RSI confirmation")
        if candle.direction_match:
            reasons_confirm.append(f"Candlestick: {', '.join(candle.patterns) or 'direction match'}")
        if rv5 >= 1.2:
            reasons_confirm.append(f"Volume confirmation (RV {rv5:.2f})")
        if breakout.verdict.value in {"CONFIRMED BREAKOUT", "BREAKOUT RETEST"}:
            reasons_confirm.append(f"Breakout quality: {breakout.verdict.value}")
        if entry.location.value == "GOOD ENTRY ZONE":
            reasons_confirm.append("Entry zone valid")
        reasons_confirm.extend(pa_notes[:3])

        if blocks:
            reasons_reject.extend(blocks)
        if rsi.divergence_warning:
            reasons_reject.append("RSI momentum disagreement")
        if volume.weak_participation:
            reasons_reject.append(f"Weak volume confirmation (RV {rv5:.2f})")
        if entry.location.value == "LATE ENTRY":
            reasons_reject.append("Late entry - impulse largely consumed")
        if trap.detected:
            reasons_reject.extend(f.name for f in trap.findings[:3])
        if rv15 < 0.8:
            reasons_reject.append(f"15M volume below threshold (RV {rv15:.2f})")

        verdict, decision = decide_verdict(
            confirmation, risk, blocks, breakout, trap, entry, reasons_confirm, reasons_reject
        )
        return ConfirmationVerdict(
            verdict=verdict,
            confirmation=confirmation,
            risk=risk,
            entry_location=entry,
            breakout=breakout,
            trap=trap,
            rsi=rsi,
            candle=candle,
            volume=volume,
            mtf=mtf,
            reasons_confirm=reasons_confirm,
            reasons_reject=reasons_reject,
            hard_blocks=blocks,
            countertrend=mtf.countertrend,
            decision=decision,
        )

    def recheck(
        self,
        symbol: str,
        signal_id: str,
        previous: EntryVerdict,
        direction: str,
        frames: dict[str, pd.DataFrame],
        plan: TradePlan,
        now_ms: int | None = None,
    ) -> RecheckResult:
        """Re-evaluate an EARLY_ENTRY after the next candle closes.

        Historical signal outcomes are never rewritten - only the forward
        confirmation status may move EARLY -> CONFIRMED or -> INVALIDATED.
        """
        current = self.evaluate(symbol, direction, frames, plan, now_ms)
        closed_ts = int(frames[TRIGGER_TIMEFRAME]["timestamp"].iloc[-1]) if not frames.get(TRIGGER_TIMEFRAME, pd.DataFrame()).empty else 0
        reasons = list(current.reasons_confirm) or list(current.reasons_reject)
        if current.hard_blocks or current.verdict == EntryVerdict.WEAK_SIGNAL:
            return RecheckResult(signal_id, previous, EntryVerdict.INVALIDATED, False, True, reasons, closed_ts)
        if current.confirmation.total >= 80 and current.risk.score <= 40:
            return RecheckResult(signal_id, previous, EntryVerdict.CONFIRMED_ENTRY, True, False, reasons, closed_ts)
        return RecheckResult(signal_id, previous, EntryVerdict.EARLY_ENTRY, False, False, reasons, closed_ts)

    def _empty_verdict(self, reason: str) -> ConfirmationVerdict:
        from app.false_signal.models import (
            CandleConfirmationResult,
            ConfirmationScore,
            EntryQualityResult,
            FalseBreakoutResult,
            LiquidityTrapResult,
            MTFConfirmationResult,
            RSIConfirmationResult,
            VolumeConfirmationResult,
        )
        from app.false_signal.models import BreakoutVerdict, EntryLocation, MTFAlignment

        score = ConfirmationScore()
        risk = build_false_signal_risk(
            FalseBreakoutResult(verdict=BreakoutVerdict.NO_BREAKOUT),
            LiquidityTrapResult(), RSIConfirmationResult(), CandleConfirmationResult(),
            VolumeConfirmationResult(), MTFConfirmationResult(alignment=MTFAlignment.CONFLICT),
            EntryQualityResult(location=EntryLocation.ENTRY_INVALIDATED), 100,
        )
        return ConfirmationVerdict(
            verdict=EntryVerdict.NO_TRADE, confirmation=score, risk=risk,
            entry_location=EntryQualityResult(location=EntryLocation.ENTRY_INVALIDATED),
            breakout=FalseBreakoutResult(verdict=BreakoutVerdict.NO_BREAKOUT),
            trap=LiquidityTrapResult(), rsi=RSIConfirmationResult(),
            candle=CandleConfirmationResult(closed=False), volume=VolumeConfirmationResult(),
            mtf=MTFConfirmationResult(alignment=MTFAlignment.CONFLICT),
            reasons_reject=[reason], hard_blocks=[reason], decision="NO TRADE",
        )


def format_rejected_from_dict(symbol: str, direction: str, data: dict) -> str:
    """Format a rejection from the serialised diagnostics carried by EngineResult."""
    lines = ["⚠️ SIGNAL REJECTED", "", f"Symbol: {symbol}", f"Direction: {direction}", "", "Reason:"]
    reasons = data.get("reasons_reject") or data.get("hard_blocks") or []
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(
        [
            "",
            f"Confirmation Score: {float(data.get('confirmation_score', 0)):.1f}/100",
            f"False Signal Risk: {data.get('false_signal_risk', 0)}/100 "
            f"({data.get('risk_category', 'n/a')})",
            "",
            "Decision: NO TRADE.",
        ]
    )
    return "\n".join(lines)


def format_rejected(symbol: str, direction: str, verdict: ConfirmationVerdict) -> str:
    lines = [
        "⚠️ SIGNAL REJECTED",
        f"Symbol: {symbol}",
        f"Direction: {direction}",
        "",
        "Reason:",
    ]
    lines.extend(f"- {reason}" for reason in (verdict.reasons_reject or verdict.hard_blocks))
    lines.extend([
        "",
        f"False Signal Risk: {verdict.risk.score}/100 ({verdict.risk.category.value})",
        "Decision: NO TRADE.",
    ])
    return "\n".join(lines)

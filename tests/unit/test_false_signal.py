"""Unit tests for false signal detection sub-engines."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.constants import LONG, SHORT
from app.false_signal.candle_confirmation import confirm_candle
from app.false_signal.false_breakout import breakout_score, detect_false_breakout
from app.false_signal.liquidity_trap import detect_liquidity_trap
from app.false_signal.models import (
    BreakoutVerdict,
    ConfidenceCategory,
    EntryLocation,
    EntryVerdict,
    MTFAlignment,
    RiskCategory,
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
from tests.factories import BASE_TS, candle, make_candles, make_frame


def bar(i, o, h, l, c, v=1000, closed=True):
    return candle(BASE_TS + i * 300_000, o, h, l, c, v, closed)


# --- False breakout ---------------------------------------------------------

def test_confirmed_breakout() -> None:
    candles = [bar(0, 98, 99, 97, 98.5), bar(1, 99, 102, 98.8, 101), bar(2, 101, 102, 100.8, 101.5)]
    result = detect_false_breakout(candles, LONG, 100.0, 2.0, 1.5)
    assert result.verdict == BreakoutVerdict.CONFIRMED_BREAKOUT
    assert breakout_score(result) == 10.0


def test_failed_breakout_needs_more_than_return() -> None:
    candles = [bar(0, 99, 102, 98.8, 101), bar(1, 101, 101.5, 98.5, 99), bar(2, 99, 99.5, 98, 98.8)]
    result = detect_false_breakout(candles, LONG, 100.0, 2.0, 0.8)
    assert result.verdict == BreakoutVerdict.FAILED_BREAKOUT
    assert result.returned_inside
    assert breakout_score(result) == 0.0


def test_volume_backed_retest_not_false() -> None:
    candles = [bar(0, 99, 102, 98.8, 101), bar(1, 101, 101.5, 99.7, 100.6), bar(2, 100.6, 102, 100.2, 101.4)]
    result = detect_false_breakout(candles, LONG, 100.0, 1.0, 1.6)
    assert result.verdict == BreakoutVerdict.BREAKOUT_RETEST


def test_liquidity_sweep_and_stop_hunt() -> None:
    candles = [bar(0, 98, 99, 97, 98.5), bar(1, 98, 102, 97, 99)]
    sweep = detect_false_breakout(candles, LONG, 100.0, 2.0, 1.0)
    assert sweep.verdict == BreakoutVerdict.LIQUIDITY_SWEEP
    hunt = detect_false_breakout(candles, LONG, 100.0, 2.0, 1.8)
    assert hunt.verdict == BreakoutVerdict.STOP_HUNT_CANDIDATE


def test_short_breakout_mirror() -> None:
    candles = [bar(0, 102, 103, 101, 102), bar(1, 101, 102, 98.8, 99)]
    result = detect_false_breakout(candles, SHORT, 100.0, 2.0, 1.5)
    assert result.verdict == BreakoutVerdict.CONFIRMED_BREAKOUT


def test_unclosed_bar_ignored() -> None:
    candles = [bar(0, 99, 102, 98.8, 101), bar(1, 99, 99, 99, 99, closed=False)]
    result = detect_false_breakout(candles, LONG, 100.0, 2.0, 1.5)
    assert result.verdict == BreakoutVerdict.CONFIRMED_BREAKOUT


# --- Liquidity trap ---------------------------------------------------------

def pa_stub(highs=None, lows=None):
    return SimpleNamespace(
        swing_highs=[SimpleNamespace(price=p) for p in (highs or [])],
        swing_lows=[SimpleNamespace(price=p) for p in (lows or [])],
        supports=[],
        resistances=[],
    )


def test_single_wick_is_not_strong_trap() -> None:
    candles = [bar(i, 100, 100.6, 99.6, 100) for i in range(3)]
    trap = detect_liquidity_trap(candles, LONG, pa_stub([101, 101.01]), SimpleNamespace(verdict=BreakoutVerdict.NO_BREAKOUT, retest=False, returned_inside=False, volume_confirmed=False, detail=""), 2.0, 1.1)
    assert not trap.strong
    assert any(f.name == "Equal highs" for f in trap.findings)


def test_sweep_high_creates_trap_evidence() -> None:
    candles = [bar(i, 100, 100.5, 99.5, 100) for i in range(3)] + [bar(3, 100, 103, 99.5, 100.2)]
    trap = detect_liquidity_trap(candles, LONG, pa_stub([102]), SimpleNamespace(verdict=BreakoutVerdict.NO_BREAKOUT, retest=False, returned_inside=False, volume_confirmed=False, detail=""), 2.0, 1.0)
    assert trap.detected
    assert any(f.name == "Sweep of previous high" for f in trap.findings)


def test_false_breakout_makes_trap_strong() -> None:
    candles = [bar(i, 100, 101, 99, 100) for i in range(3)] + [bar(3, 100, 106, 96, 100.5)]
    false_bo = SimpleNamespace(verdict=BreakoutVerdict.FAILED_BREAKOUT, retest=True, returned_inside=True, volume_confirmed=False, detail="failed")
    trap = detect_liquidity_trap(candles, LONG, pa_stub(highs=[101, 101.01]), false_bo, 2.0, 1.6)
    assert trap.strong
    assert any(f.name == "False resistance break" for f in trap.findings)


# --- RSI --------------------------------------------------------------------

def test_rsi_bullish_confirmation() -> None:
    frame = make_frame(make_candles(120, start=100, drift=0.001))
    result = confirm_rsi(frame, LONG, "15m")
    assert 0 <= result.score <= 15
    assert isinstance(result.bullish_confirmation, bool)
    assert result.detail


def test_rsi_momentum_weakness_for_long() -> None:
    frame = make_frame(make_candles(120, start=100, drift=-0.002))
    result = confirm_rsi(frame, LONG, "15m")
    assert result.momentum_weakness or result.divergence_warning or result.score < 10


# --- Candle -----------------------------------------------------------------

def test_candle_requires_closed_bar() -> None:
    candles = [bar(0, 100, 101, 99, 100), bar(1, 100, 102, 99, 101, closed=False)]
    result = confirm_candle(candles, LONG, pa_stub(), 1.5, 2.0)
    assert not result.confirmed
    assert "Insufficient" in result.detail


def test_candle_direction_match_and_volume() -> None:
    candles = [bar(0, 100, 101, 97, 98), bar(1, 97, 106, 96, 105)]
    result = confirm_candle(candles, LONG, pa_stub(), 1.5, 2.0)
    assert result.direction_match
    assert result.volume_ok
    assert result.confirmed


# --- Volume -----------------------------------------------------------------

def test_volume_weak_participation() -> None:
    frame = make_frame(make_candles(60, drift=0.001))
    frame.loc[frame.index[-1], "volume"] = 100.0
    result = confirm_volume(frame, LONG, SimpleNamespace(volume_confirmed=False))
    assert result.weak_participation
    assert result.score <= 2


def test_volume_spike() -> None:
    frame = make_frame(make_candles(60, drift=0.001))
    frame.loc[frame.index[-1], "volume"] = 10000.0
    result = confirm_volume(frame, LONG, SimpleNamespace(volume_confirmed=True))
    assert result.spike
    assert result.score > 5


# --- MTF --------------------------------------------------------------------

def test_mtf_full_alignment_bullish() -> None:
    frames = {
        tf: make_frame(make_candles(120, start=100, drift=0.01))
        for tf in ("1d", "4h", "1h", "15m", "5m")
    }
    result = confirm_mtf(frames, LONG)
    assert result.alignment in {MTFAlignment.FULL, MTFAlignment.PARTIAL}
    assert 0 <= result.score <= 20


def test_mtf_countertrend_detected() -> None:
    frames = {
        "1d": make_frame(make_candles(120, start=100, drift=0.01)),
        "4h": make_frame(make_candles(120, start=100, drift=0.01)),
        "1h": make_frame(make_candles(120, start=100, drift=-0.01)),
        "15m": make_frame(make_candles(120, start=100, drift=-0.01)),
        "5m": make_frame(make_candles(120, start=100, drift=-0.01)),
    }
    result = confirm_mtf(frames, SHORT)
    assert result.alignment in {MTFAlignment.CONFLICT, MTFAlignment.COUNTERTREND, MTFAlignment.REVERSAL}
    assert result.countertrend or result.alignment == MTFAlignment.REVERSAL


# --- Scoring and verdicts ---------------------------------------------------

def test_confirmation_score_caps_and_categories() -> None:
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
    score = build_confirmation_score(
        MTFConfirmationResult(score=20), 15,
        RSIConfirmationResult(score=15), CandleConfirmationResult(score=15),
        VolumeConfirmationResult(score=10),
        FalseBreakoutResult(verdict=BreakoutVerdict.CONFIRMED_BREAKOUT),
        EntryQualityResult(score=10), 5,
    )
    assert score.total == 100
    assert score.category == ConfidenceCategory.STRONG
    assert ConfirmationScore().category == ConfidenceCategory.WEAK


def test_risk_categories() -> None:
    from app.false_signal.models import FalseSignalRisk

    assert FalseSignalRisk(score=10).category == RiskCategory.LOW
    assert FalseSignalRisk(score=30).category == RiskCategory.MODERATE
    assert FalseSignalRisk(score=50).category == RiskCategory.ELEVATED
    assert FalseSignalRisk(score=70).category == RiskCategory.HIGH
    assert FalseSignalRisk(score=90).category == RiskCategory.VERY_HIGH


def test_hard_rules_override_score() -> None:
    from app.false_signal.models import (
        CandleConfirmationResult,
        EntryQualityResult,
        FalseBreakoutResult,
        LiquidityTrapResult,
        MTFConfirmationResult,
    )
    blocks = hard_rejection_checks(
        FalseBreakoutResult(verdict=BreakoutVerdict.FAILED_BREAKOUT, detail="failed"),
        LiquidityTrapResult(detected=True, strength=0.8, detail="trap"),
        MTFConfirmationResult(alignment=MTFAlignment.CONFLICT),
        CandleConfirmationResult(closed=True),
        EntryQualityResult(location=EntryLocation.ENTRY_INVALIDATED),
        True, 2.0,
    )
    assert len(blocks) >= 4
    from app.false_signal.models import ConfirmationScore, FalseSignalRisk
    verdict, decision = decide_verdict(
        ConfirmationScore(multi_timeframe=20, rsi=15), FalseSignalRisk(score=5), blocks,
        FalseBreakoutResult(verdict=BreakoutVerdict.FAILED_BREAKOUT),
        LiquidityTrapResult(detected=True, strength=0.8),
        EntryQualityResult(location=EntryLocation.ENTRY_INVALIDATED), [], [],
    )
    assert verdict == EntryVerdict.FALSE_BREAKOUT
    assert decision == "NO TRADE"


@pytest.mark.parametrize(
    "total,risk,expected",
    [
        (92, 10, EntryVerdict.STRONG_ENTRY),
        (85, 30, EntryVerdict.CONFIRMED_ENTRY),
        (72, 45, EntryVerdict.EARLY_ENTRY),
        (60, 20, EntryVerdict.WEAK_SIGNAL),
    ],
)
def test_verdict_thresholds(total, risk, expected) -> None:
    from app.false_signal.models import (
        ConfirmationScore,
        EntryQualityResult,
        FalseBreakoutResult,
        FalseSignalRisk,
        LiquidityTrapResult,
    )
    verdict, _ = decide_verdict(
        ConfirmationScore(multi_timeframe=total),
        FalseSignalRisk(score=risk), [],
        FalseBreakoutResult(verdict=BreakoutVerdict.NO_BREAKOUT),
        LiquidityTrapResult(), EntryQualityResult(), [], [],
    )
    assert verdict == expected

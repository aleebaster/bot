"""Market structure tests: swings, BOS/CHoCH, levels, sweeps."""

from __future__ import annotations

from app.price_action.structure import (
    BEARISH,
    BULLISH,
    RANGING,
    analyze,
    classify_swings,
    detect_bos_choch,
    find_levels,
    find_swings,
    structure_trend,
)
from tests.factories import BASE_TS, candle, make_candles


def test_find_swings_identifies_highs_and_lows() -> None:
    candles = [
        candle(BASE_TS + i, 100, 100 + (10 if i == 5 else 0), 100 - (10 if i == 10 else 0), 100)
        for i in range(16)
    ]
    highs, lows = find_swings(candles, order=2)
    assert any(s.index == 5 for s in highs)
    assert any(s.index == 10 for s in lows)


def test_classify_swings() -> None:
    from app.price_action.structure import Swing

    swings = [
        Swing(0, 0, 100, "low"), Swing(1, 0, 110, "low"),
        Swing(2, 0, 105, "high"), Swing(3, 0, 115, "high"),
    ]
    assert classify_swings(swings) == ["", "HL", "", "HH"]


def test_structure_trend_bullish() -> None:
    from app.price_action.structure import Swing

    highs = [Swing(0, 0, 100, "high"), Swing(1, 0, 110, "high"), Swing(2, 0, 120, "high")]
    lows = [Swing(0, 0, 90, "low"), Swing(1, 0, 100, "low"), Swing(2, 0, 110, "low")]
    assert structure_trend(highs, lows) == BULLISH


def test_structure_trend_bearish() -> None:
    from app.price_action.structure import Swing

    highs = [Swing(0, 0, 120, "high"), Swing(1, 0, 110, "high"), Swing(2, 0, 100, "high")]
    lows = [Swing(0, 0, 110, "low"), Swing(1, 0, 100, "low"), Swing(2, 0, 90, "low")]
    assert structure_trend(highs, lows) == BEARISH


def test_bos_detected_on_breakout() -> None:
    candles = make_candles(40, start=100, drift=0.002, wave=0.01)
    highs, lows = find_swings(candles, order=2)
    events = detect_bos_choch(candles, highs, lows)
    assert any(e.kind in {"BOS", "CHoCH"} for e in events)
    assert any(e.direction == BULLISH for e in events)


def test_support_resistance_from_reactions() -> None:
    candles = make_candles(80, start=100, drift=0.0005, wave=0.02)
    highs, lows = find_swings(candles, order=2)
    supports, resistances = find_levels(candles, highs, lows)
    assert all(s.price < candles[-1].close for s in supports)
    assert all(r.price > candles[-1].close for r in resistances)


def test_liquidity_sweep_detected() -> None:
    base = make_candles(20, start=100, drift=0.0)
    # Prior swing low around 90, then a wick below it that closes back above.
    last = candle(BASE_TS + 21, 99.8, 100.15, 88, 100.1)
    result = analyze(base + [last], order=2)
    assert result.sweep is not None
    assert result.sweep.direction == BULLISH


def test_analyze_returns_ranging_on_short_series() -> None:
    result = analyze(make_candles(5), order=2)
    assert result.trend == RANGING
    assert result.events == []

"""Candlestick pattern recognition tests."""

from __future__ import annotations

import pytest

from app.candle_patterns.detector import BEARISH, BULLISH, best_pattern, detect_patterns, metrics, recent_trend
from tests.factories import BASE_TS, candle, make_candles


def test_candle_metrics() -> None:
    m = metrics(candle(0, 100, 110, 95, 105, v=100))
    assert m.body == 5
    assert m.upper_wick == 5
    assert m.lower_wick == 5
    assert m.body_ratio == pytest.approx(1 / 3)


def test_bullish_engulfing_detected() -> None:
    candles = [
        candle(BASE_TS, 100, 101, 97, 98),
        candle(BASE_TS + 1, 97, 106, 96, 105),
    ]
    names = {p.name for p in detect_patterns(candles)}
    assert "Bullish Engulfing" in names


def test_bearish_engulfing_detected() -> None:
    candles = [
        candle(BASE_TS, 98, 106, 97, 105),
        candle(BASE_TS + 1, 106, 107, 96, 97),
    ]
    names = {p.name for p in detect_patterns(candles)}
    assert "Bearish Engulfing" in names


def test_hammer_detected_in_downtrend() -> None:
    candles = make_candles(8, start=110, drift=-0.01)
    candles.append(candle(BASE_TS + 9, 100, 100.5, 90, 100.4))
    names = {p.name for p in detect_patterns(candles)}
    assert "Hammer" in names


def test_shooting_star_detected_in_uptrend() -> None:
    candles = make_candles(8, start=90, drift=0.01)
    candles.append(candle(BASE_TS + 9, 100, 110, 99.5, 99.7))
    names = {p.name for p in detect_patterns(candles)}
    assert "Shooting Star" in names


def test_doji_detected() -> None:
    candles = [candle(BASE_TS + i, 100, 100.1, 99.9, 100.0) for i in range(5)]
    names = {p.name for p in detect_patterns(candles)}
    assert "Doji" in names


def test_inside_and_outside_bar() -> None:
    inside = [candle(BASE_TS, 100, 105, 95, 101), candle(BASE_TS + 1, 100, 104, 96, 102)]
    assert "Inside Bar" in {p.name for p in detect_patterns(inside)}
    outside = [candle(BASE_TS, 100, 104, 96, 102), candle(BASE_TS + 1, 100, 108, 92, 101)]
    assert "Outside Bar" in {p.name for p in detect_patterns(outside)}


def test_three_white_soldiers() -> None:
    candles = [
        candle(BASE_TS, 100, 104, 99, 103),
        candle(BASE_TS + 1, 103, 108, 102, 107),
        candle(BASE_TS + 2, 107, 113, 106, 112),
    ]
    assert "Three White Soldiers" in {p.name for p in detect_patterns(candles)}


def test_best_pattern_filters_direction() -> None:
    candles = [
        candle(BASE_TS, 100, 101, 97, 98),
        candle(BASE_TS + 1, 97, 106, 96, 105),
    ]
    result = best_pattern(candles, BULLISH)
    assert result is not None and result.direction == BULLISH
    assert best_pattern(candles, BEARISH) is None


def test_recent_trend_direction() -> None:
    up = make_candles(10, drift=0.01)
    down = make_candles(10, drift=-0.01)
    assert recent_trend(up) == 1
    assert recent_trend(down) == -1

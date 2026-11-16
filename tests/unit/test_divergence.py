"""RSI pivot and divergence classification tests."""

from __future__ import annotations

import pandas as pd

from app.indicators.divergence import RSIState, analyze_rsi, detect_divergences, find_pivots, rsi_state_at
from app.indicators.technical import rsi


def test_find_pivots_ignores_edges() -> None:
    series = pd.Series([1, 2, 3, 5, 3, 2, 1, 0, 1, 3, 2, 1], dtype=float)
    highs = find_pivots(series, order=2, mode="high")
    lows = find_pivots(series, order=2, mode="low")
    assert any(i == 3 for i, _ in highs)
    assert all(2 <= i < len(series) - 2 for i, _ in highs + lows)


def test_rsi_state_from_series() -> None:
    r7 = pd.Series([70.0] * 20)
    r14 = pd.Series([65.0] * 20)
    r21 = pd.Series([55.0] * 20)
    state = rsi_state_at(r7, r14, r21, 19)
    assert isinstance(state, RSIState)
    assert state.above_50 and state.momentum_up
    assert state.value == 65.0


def test_rsi_cross_and_exit_flags() -> None:
    r14 = pd.Series([29.0, 31.0, 55.0])
    state = rsi_state_at(r14, r14, r14, 1)
    assert state.exit_oversold
    state2 = rsi_state_at(r14, r14, r14, 2)
    assert state2.crossed_above_50


def test_regular_bullish_divergence(monkeypatch) -> None:
    close = pd.Series([100, 95, 90, 93, 96, 92, 85, 90, 94, 97], dtype=float)
    # Price makes a lower low (90 -> 85) while RSI makes a higher low (25 -> 40).
    custom = pd.Series([50, 48, 25, 49, 52, 47, 40, 50, 53, 55], dtype=float)
    monkeypatch.setattr("app.indicators.divergence.rsi", lambda series, period: custom)
    found = detect_divergences(pd.DataFrame({"close": close}), "15m", 4, order=2, lookback=20)
    assert any(d.kind == "bullish" for d in found)


def test_no_divergence_on_flat_series() -> None:
    frame = pd.DataFrame({"close": [100.0] * 60})
    assert detect_divergences(frame, "15m", 14) == []


def test_analyze_rsi_oversold_flag() -> None:
    frame = pd.DataFrame({"close": [100 - i for i in range(40)] + [60] * 5})
    state = analyze_rsi(frame, "5m")
    assert state.value is not None
    assert state.oversold

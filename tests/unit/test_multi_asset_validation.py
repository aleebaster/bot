"""Tests for the multi-asset validation helpers (no network required)."""

from __future__ import annotations

import pandas as pd

from scripts.multi_asset_validation import aggregate_frame, bootstrap_ci, classify_regime
from tests.factories import make_candles, make_frame


def test_bootstrap_ci_is_deterministic_and_brackets_mean() -> None:
    values = [1.0, -1.0, 0.5, 2.0, -0.5]
    a = bootstrap_ci(values)
    b = bootstrap_ci(values)
    assert a == b
    assert a["n"] == 5
    assert a["ci_low"] <= a["mean"] <= a["ci_high"]


def test_bootstrap_ci_empty() -> None:
    assert bootstrap_ci([])["n"] == 0


def test_aggregate_frame_drops_partial_group() -> None:
    frame = make_frame(make_candles(410, drift=0.001))
    hourly = aggregate_frame(frame, 4)
    assert len(hourly) == 102  # floor(410/4), the last 2 bars are ignored
    assert float(hourly["close"].iloc[-1]) == float(frame["close"].iloc[407])


def test_regime_classification_ignores_future_bars() -> None:
    frame = make_frame(make_candles(900, start=100, drift=0.001, wave=0.01))
    index = 600
    before = classify_regime(frame, index, "LONG")

    future = make_candles(200, start=float(frame["close"].iloc[-1]), drift=-0.02)
    extended = pd.concat([frame, make_frame(future)], ignore_index=True)
    after = classify_regime(extended, index, "LONG")
    assert before == after


def test_regime_labels_are_known() -> None:
    frame = make_frame(make_candles(900, start=100, drift=0.01))
    result = classify_regime(frame, 700, "LONG")
    assert result["primary"] in {"bull", "bear", "sideways", "unknown"}
    assert result["volatility"] in {"high", "low", "normal", "unknown"}
    assert isinstance(result["reversal"], bool)

"""Indicator math checks against known reference values and invariants."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.indicators.technical import IndicatorSet, adx, atr, ema, rsi, sma, true_range, vwap

# Classic Wilder RSI example (StockCharts): first 14-period RSI = 70.46.
WILDER_CLOSES = [
    44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
    45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
]


def test_rsi_matches_wilder_reference() -> None:
    value = rsi(pd.Series(WILDER_CLOSES), 14).iloc[-1]
    assert value == pytest.approx(70.46, abs=0.02)


def test_rsi_bounds_and_warmup() -> None:
    series = pd.Series(np.linspace(90, 110, 100) + np.sin(np.arange(100)) * 5)
    values = rsi(series, 14)
    assert values.iloc[:14].isna().all()
    assert values.dropna().between(0, 100).all()


def test_rsi_flat_series_is_50() -> None:
    assert rsi(pd.Series([100.0] * 30), 14).iloc[-1] == pytest.approx(50.0)


def test_ema_matches_pandas_ewm() -> None:
    series = pd.Series(range(50), dtype=float)
    expected = series.ewm(span=9, adjust=False).mean()
    pd.testing.assert_series_equal(ema(series, 9), expected)


def test_sma_returns_nan_during_warmup() -> None:
    series = pd.Series(range(30), dtype=float)
    result = sma(series, 10)
    assert result.iloc[:9].isna().all()
    assert result.iloc[9] == pytest.approx(4.5)


def test_true_range_uses_previous_close() -> None:
    frame = pd.DataFrame({"high": [10, 12, 11], "low": [9, 10, 8], "close": [9.5, 11, 8.5]})
    tr = true_range(frame)
    assert tr.iloc[0] == 1.0
    assert tr.iloc[1] == pytest.approx(2.5)  # 12 - 9.5
    assert tr.iloc[2] == pytest.approx(3.0)  # 11 - 8


def test_atr_is_positive_and_stabilises() -> None:
    frame = pd.DataFrame(
        {
            "high": [100 + i * 0.5 + 1 for i in range(60)],
            "low": [100 + i * 0.5 - 1 for i in range(60)],
            "close": [100 + i * 0.5 for i in range(60)],
        }
    )
    values = atr(frame, 14)
    assert values.iloc[:14].isna().all()
    assert values.dropna().gt(0).all()


def test_adx_direction_columns() -> None:
    n = 100
    frame = pd.DataFrame(
        {
            "high": [100 + i for i in range(n)],
            "low": [99 + i for i in range(n)],
            "close": [99.5 + i for i in range(n)],
        }
    )
    result = adx(frame, 14)
    assert set(result.columns) == {"adx", "plus_di", "minus_di"}
    assert result["plus_di"].dropna().iloc[-1] > result["minus_di"].dropna().iloc[-1]
    assert result["adx"].dropna().iloc[-1] > 0


def test_vwap_is_volume_weighted() -> None:
    frame = pd.DataFrame(
        {"high": [10, 12], "low": [8, 10], "close": [9, 11], "volume": [1.0, 3.0]}
    )
    values = vwap(frame)
    assert values.iloc[0] == pytest.approx(9.0)
    # typical prices: 9 and 11 -> (9*1 + 11*3) / 4 = 10.5
    assert values.iloc[1] == pytest.approx((9 * 1 + 11 * 3) / 4)


def test_indicator_set_snapshot_has_all_keys() -> None:
    from tests.factories import make_candles, make_frame

    frame = make_frame(make_candles(300, drift=0.001, wave=0.01))
    snapshot = IndicatorSet.from_frame(frame).snapshot()
    for key in ("ema9", "ema21", "ema50", "ema200", "vwap", "atr14", "adx", "rsi7", "rsi14", "rsi21", "volume_sma20"):
        assert key in snapshot
    assert snapshot["rsi14"] is not None

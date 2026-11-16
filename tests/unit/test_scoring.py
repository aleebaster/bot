"""Scoring component and category tests."""

from __future__ import annotations

from app.signal_engine.models import ScoreBreakdown
from app.signal_engine.scoring import _volume_info
from tests.factories import make_candles, make_frame


def test_score_breakdown_categories() -> None:
    assert ScoreBreakdown(multi_timeframe_trend=20, rsi=15, candlestick=15, market_structure=15,
                          support_resistance=10, volume=10, ema_vwap=10, volatility_entry=5).category == "Excellent"
    assert ScoreBreakdown(multi_timeframe_trend=20, rsi=15, candlestick=10, market_structure=10,
                          support_resistance=8, volume=8, ema_vwap=8, volatility_entry=5).category == "Strong"
    assert ScoreBreakdown(multi_timeframe_trend=16, rsi=12, candlestick=12, market_structure=11,
                          support_resistance=7, volume=7, ema_vwap=7, volatility_entry=4).category == "Moderate"
    assert ScoreBreakdown().category == "Ignore"


def test_score_breakdown_total_and_dict() -> None:
    breakdown = ScoreBreakdown(multi_timeframe_trend=20, rsi=10)
    assert breakdown.total == 30
    assert breakdown.as_dict()["total"] == 30


def test_volume_info() -> None:
    candles = make_candles(40, drift=0.001)
    candles[-1] = type(candles[-1])(**{**candles[-1].to_dict(), "volume": 5000.0})
    frame = make_frame(candles)
    relative, current = _volume_info(frame)
    assert current == 5000.0
    assert relative > 1.0

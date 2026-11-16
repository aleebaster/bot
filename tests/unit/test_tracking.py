"""Chronological SL/TP resolution, MFE/MAE and fee-adjusted R tests."""

from __future__ import annotations

from app.database.tracking import SignalTracker, TrackedSetup
from app.risk_management.position import CostModel
from tests.factories import BASE_TS, candle

COSTS = CostModel(taker_fee=0.0004, maker_fee=0.0002, slippage=0.0005, funding_per_8h=0.0001)


def setup(**overrides) -> TrackedSetup:
    params = dict(
        symbol="BTCUSDT", direction="LONG", entry=100.0, stop_loss=98.0,
        tp1=102.0, tp2=104.0, tp3=106.0, risk_usdt=5.0, notional=250.0,
        expiration=10**15, timestamp=BASE_TS,
    )
    params.update(overrides)
    return TrackedSetup(**params)


def test_sl_before_tp_is_loss() -> None:
    candles = [
        candle(BASE_TS, 100, 101.5, 99, 100.5),
        candle(BASE_TS + 1, 100.5, 101.5, 97.5, 98.5),
    ]
    update = SignalTracker(COSTS).track(setup(), candles)
    assert update.outcome == "SL"
    assert update.realized_r < -1.0  # fees added to loss
    assert update.mae > 0


def test_same_bar_sl_takes_priority() -> None:
    candles = [candle(BASE_TS, 100, 107, 97, 101)]
    update = SignalTracker(COSTS).track(setup(), candles)
    assert update.outcome == "SL"


def test_tp3_after_tp1_sequence() -> None:
    candles = [
        candle(BASE_TS, 100, 102.5, 99, 101),
        candle(BASE_TS + 1, 101, 104.5, 100, 103),
        candle(BASE_TS + 2, 103, 106.5, 102, 105),
    ]
    update = SignalTracker(COSTS).track(setup(), candles)
    assert update.outcome in {"TP2", "TP3"}
    assert update.highest_tp >= 2
    assert update.mfe > 3


def test_short_direction_excursion() -> None:
    s = setup(direction="SHORT", entry=100, stop_loss=102, tp1=98, tp2=96, tp3=94)
    candles = [candle(BASE_TS, 100, 101, 97, 99)]
    update = SignalTracker(COSTS).track(s, candles)
    assert update.mfe > 0
    assert update.outcome in {"OPEN", "TP1", "TP2", "TP3"}


def test_expiry_when_no_trigger() -> None:
    s = setup(expiration=BASE_TS)
    candles = [candle(BASE_TS, 100, 100.5, 99.5, 100)]
    update = SignalTracker(COSTS).track(s, candles)
    assert update.outcome == "EXPIRED"

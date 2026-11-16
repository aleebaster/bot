"""Backtesting engine and metrics tests with deterministic synthetic data."""

from __future__ import annotations

from app.backtesting.engine import Backtester
from app.backtesting.metrics import BacktestTrade, compute_metrics
from app.config import Settings
from app.market_data.models import candles_to_frame
from tests.factories import BASE_TS, candle


def make_data(n: int = 600):
    candles = []
    price = 100.0
    for i in range(n):
        open_price = price
        phase = i % 10
        if phase == 5:
            close, high, low = open_price * 0.997, open_price * 1.001, open_price * 0.998
        elif phase == 6:
            close, high, low = open_price * 1.012, open_price * 1.013, open_price * 0.998
        else:
            close, high, low = open_price * 1.0008, open_price * 1.001, open_price * 0.999
        volume = 3000 if phase == 6 else 1000
        candles.append(candle(BASE_TS + i * 900_000, open_price, high, low, close, volume))
        price = close
    return candles_to_frame(candles)


def test_metrics_on_empty() -> None:
    assert compute_metrics([])["trades"] == 0
    assert compute_metrics([])["expectancy_r"] == 0.0


def test_metrics_calculation() -> None:
    trades = [
        BacktestTrade("BTCUSDT", "LONG", 0, 0, 1, 100, 98, 102, 104, 106, "TP1", 1, 0.9, 0.1, 2, 0.5, 1),
        BacktestTrade("BTCUSDT", "LONG", 1, 0, 2, 100, 98, 102, 104, 106, "SL", -1, -1.1, 0.1, 0.5, 2, 1),
    ]
    metrics = compute_metrics(trades)
    assert metrics["trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["win_rate"] == 50.0
    assert metrics["expectancy_r"] == -0.1


def test_backtester_produces_walk_forward_splits() -> None:
    result = Backtester(Settings(min_signal_score=40)).run(make_data(), "BTCUSDT", "15m")
    assert result.bars == 600
    assert set(result.splits) == {"in_sample", "validation", "out_of_sample"}
    assert "BACKTEST REPORT" in result.as_report()


def test_backtester_no_lookahead_entry() -> None:
    result = Backtester(Settings(min_signal_score=40)).run(make_data(), "BTCUSDT", "15m")
    assert all(t.entry_index > 200 for t in result.trades)
    assert all(t.exit_ts >= t.entry_ts for t in result.trades)

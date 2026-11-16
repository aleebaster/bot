"""Regression tests for caching, no-look-ahead and continuous-scan controls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from app.config import Settings
from app.market_data.models import freshness_limit_seconds
from app.scheduler.scheduler import ScanScheduler


def test_freshness_limit_scales_with_timeframe() -> None:
    assert freshness_limit_seconds("5m", 180) == 660
    assert freshness_limit_seconds("1d", 180) == 172_860
    assert freshness_limit_seconds("5m", 1000) == 1000


def test_indicator_causality_on_prefix() -> None:
    from app.indicators.technical import IndicatorSet
    from tests.factories import make_candles, make_frame

    frame = make_frame(make_candles(300, drift=0.001, wave=0.01))
    i = len(frame) - 3
    full = IndicatorSet.from_frame(frame)
    prefix = IndicatorSet.from_frame(frame.iloc[: i + 1].copy())
    for field in ("ema9", "ema21", "ema50", "ema200", "rsi7", "rsi14", "rsi21", "atr14", "vwap"):
        left = float(getattr(full, field).iloc[i])
        right = float(getattr(prefix, field).iloc[-1])
        assert abs(left - right) < 1e-9, field


def test_cached_indicators_match_uncached() -> None:
    import app.indicators.technical as tech
    from tests.factories import make_candles, make_frame

    frame = make_frame(make_candles(260, drift=0.001, wave=0.01))
    tech._INDICATOR_CACHE.clear()
    fresh = tech.IndicatorSet.from_frame(frame).rsi14.copy()
    cached = tech.IndicatorSet.from_frame(frame).rsi14
    pd.testing.assert_series_equal(fresh, cached)


def test_scheduler_triggers_only_on_new_closed_bar() -> None:
    settings = Settings(watchlist=["BTCUSDT"])
    store = SimpleNamespace(latest_closed_ts=lambda symbol, tf: 100)
    exchange = SimpleNamespace(now_ms=1_000_000)
    scheduler = ScanScheduler(settings, exchange, None, store, None, None, None)
    scheduler.mark_scanned_candles()
    assert scheduler.new_closed_symbols() == []
    store.latest_closed_ts = lambda symbol, tf: 200  # type: ignore[assignment]
    assert scheduler.new_closed_symbols() == ["BTCUSDT"]
    scheduler.mark_scanned_candles()
    assert scheduler.new_closed_symbols() == []


@pytest.mark.asyncio
async def test_websocket_stream_reconnects_and_updates_store() -> None:
    from app.market_data.feed import MarketDataFeed
    from app.market_data.store import CandleStore

    class FakePro:
        def __init__(self) -> None:
            self.calls = 0

        async def watch_ohlcv(self, symbol, timeframe):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("simulated disconnect")
            await asyncio.sleep(0.05)
            return [[1_800_000_000_000, 100, 101, 99, 100, 10]]

    fake_pro = FakePro()
    exchange = SimpleNamespace(
        ws_capable=True, pro_exchange=fake_pro, now_ms=1_800_000_300_000,
        ccxt_symbol=lambda s: "BTC/USDT:USDT",
    )
    settings = Settings(ws_enabled=True, max_quote_age_seconds=180)
    store = CandleStore()
    feed = MarketDataFeed(exchange, store, settings)
    feed._running = True
    task = asyncio.create_task(feed._watch("BTCUSDT", "5m"))
    await asyncio.sleep(1.4)  # first call fails, reconnect backoff is 1s
    assert fake_pro.calls >= 2
    assert store.get_closed("BTCUSDT", "5m")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_scheduler_signal_cooldown() -> None:
    settings = Settings(watchlist=["BTCUSDT"], signal_cooldown_minutes=240)
    exchange = SimpleNamespace(now_ms=1_000_000)
    scheduler = ScanScheduler(settings, exchange, None, None, None, None, None)
    assert not scheduler.in_signal_cooldown("BTCUSDT", 1_000_000)
    scheduler._last_signal_ts["BTCUSDT"] = 1_000_000 - 10 * 60_000
    assert scheduler.in_signal_cooldown("BTCUSDT", 1_000_000)
    assert not scheduler.in_signal_cooldown("BTCUSDT", 1_000_000 + 5 * 3_600_000)

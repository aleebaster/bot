"""Market data model, dedup, gap detection and freshness tests."""

from __future__ import annotations

import time

import pytest

from app.market_data.models import Candle, candles_to_frame, frame_to_candles, is_valid_candle, timeframe_to_ms
from app.market_data.store import CandleStore
from tests.factories import BASE_TS, make_candles


def test_timeframe_conversion() -> None:
    assert timeframe_to_ms("5m") == 300_000
    assert timeframe_to_ms("4h") == 14_400_000
    assert timeframe_to_ms("1d") == 86_400_000


def test_candle_frame_roundtrip() -> None:
    candles = make_candles(10)
    frame = candles_to_frame(candles)
    assert len(frame) == 10
    assert frame.index.is_monotonic_increasing
    restored = frame_to_candles(frame)
    assert restored[0].close == candles[0].close


def test_invalid_candle_detection() -> None:
    assert is_valid_candle(Candle(1, 100, 110, 95, 105, 10))
    assert not is_valid_candle(Candle(1, 100, 90, 95, 105, 10))  # high < body
    assert not is_valid_candle(Candle(1, 100, 110, 95, float("nan"), 10))


def test_store_deduplicates() -> None:
    store = CandleStore()
    c = Candle(BASE_TS, 100, 101, 99, 100, 10, True)
    assert store.upsert("BTCUSDT", "1m", c) is True
    assert store.upsert("BTCUSDT", "1m", c) is False


def test_closed_candle_not_overwritten_by_open() -> None:
    store = CandleStore()
    ts = BASE_TS
    store.upsert("BTCUSDT", "1m", Candle(ts, 100, 101, 99, 100, 10, True))
    changed = store.upsert("BTCUSDT", "1m", Candle(ts, 100, 110, 99, 108, 12, False))
    assert changed is False
    assert store.latest("BTCUSDT", "1m").close == 100


def test_gap_detection() -> None:
    store = CandleStore()
    step = timeframe_to_ms("1m")
    for i in (0, 1, 3, 4):
        store.upsert("BTCUSDT", "1m", Candle(BASE_TS + i * step, 100 + i, 101 + i, 99 + i, 100 + i, 10))
    gaps = store.detect_gaps("BTCUSDT", "1m")
    assert gaps == [BASE_TS + 2 * step]


def test_freshness() -> None:
    store = CandleStore()
    assert not store.is_fresh("BTCUSDT", "1m", 60)
    store.upsert("BTCUSDT", "1m", Candle(int(time.time() * 1000), 1, 1, 1, 1, 1))
    assert store.is_fresh("BTCUSDT", "1m", 60)


def test_ws_capability_uses_pro_client() -> None:
    from app.config import Settings
    from app.market_data.exchange import ExchangeClient

    client = ExchangeClient(Settings())
    assert client.ws_capable is False

    class FakePro:
        has = {"watchOHLCV": True}

        async def watch_ohlcv(self, *args, **kwargs):
            return []

    client.pro_exchange = FakePro()
    assert client.ws_capable is True
    client.pro_exchange = FakePro()
    client.pro_exchange.has = {"watchOHLCV": None}
    assert client.ws_capable is False


@pytest.mark.asyncio
async def test_fetch_ohlcv_uses_since_and_limit_keywords() -> None:
    """Regression: ccxt signature is (symbol, timeframe, since, limit)."""
    from app.config import Settings
    from app.market_data.exchange import ExchangeClient

    captured: dict = {}

    class FakeExchange:
        async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None, params=None):
            captured.update(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
            return [[BASE_TS, 100, 101, 99, 100, 10]]

    client = ExchangeClient(Settings())
    client.exchange = FakeExchange()
    candles = await client.fetch_ohlcv("BTCUSDT", "1m", limit=7, since=BASE_TS)
    assert captured["limit"] == 7
    assert captured["since"] == BASE_TS
    assert captured["symbol"] == "BTC/USDT:USDT"
    assert len(candles) == 1

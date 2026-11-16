"""WebSocket market data feed with REST backfill, reconnect and integrity checks."""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.market_data.exchange import ExchangeClient
from app.market_data.models import Candle, timeframe_to_ms
from app.market_data.store import CandleStore

logger = logging.getLogger(__name__)


class MarketDataFeed:
    """Maintains per-symbol/timeframe candle buffers from REST + WebSocket.

    Design decisions:
      * REST is used for initial load and for gap refill after a WS reconnect.
      * Only the store's closed candles are used by the analysis layer.
      * Duplicate bars are ignored by the store; missing bars trigger refill.
      * A stale stream (no message within max_quote_age_seconds) is restarted.
    """

    def __init__(self, exchange: ExchangeClient, store: CandleStore, settings: Settings) -> None:
        self.exchange = exchange
        self.store = store
        self.settings = settings
        self._tasks: dict[tuple[str, str], asyncio.Task] = {}
        self._running = False

    def _rows_to_candles(self, rows: list[list], timeframe: str) -> list[Candle]:
        step = timeframe_to_ms(timeframe)
        now = self.exchange.now_ms
        result: list[Candle] = []
        for row in rows:
            ts = int(row[0])
            o, h, l, c, v = map(float, row[1:6])
            result.append(Candle(ts, o, h, l, c, v, closed=(ts + step <= now)))
        return result

    async def backfill(
        self, symbols: list[str], timeframes: list[str], limit: int | None = None
    ) -> None:
        """Initial REST load for every requested symbol/timeframe pair."""
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    candles = await self.exchange.fetch_ohlcv(
                        symbol, timeframe, limit or self.settings.ohlcv_limit
                    )
                    added = self.store.upsert_many(symbol, timeframe, candles)
                    logger.info("Backfilled %s %s: %d new bars", symbol, timeframe, added)
                except Exception as exc:
                    logger.error("Backfill failed for %s %s: %s", symbol, timeframe, exc)

    async def refill(self, symbol: str, timeframe: str) -> None:
        """REST refill used after detecting gaps or stale data."""
        try:
            candles = await self.exchange.fetch_ohlcv(symbol, timeframe, self.settings.ohlcv_limit)
            self.store.upsert_many(symbol, timeframe, candles)
            logger.info("Refilled %s %s", symbol, timeframe)
        except Exception as exc:
            logger.warning("Refill failed for %s %s: %s", symbol, timeframe, exc)

    async def start(self, symbols: list[str], timeframes: list[str]) -> None:
        await self.backfill(symbols, timeframes)
        self._running = True
        if self.settings.ws_enabled and self.exchange.exchange is not None and self.exchange.exchange.has.get("watchOHLCV"):
            for symbol in symbols:
                for timeframe in timeframes:
                    key = (symbol, timeframe)
                    if key not in self._tasks or self._tasks[key].done():
                        self._tasks[key] = asyncio.create_task(self._watch(symbol, timeframe))
            logger.info("Started %d WebSocket candle streams", len(self._tasks))
        else:
            logger.info("WebSocket disabled/unavailable - running in REST polling mode")
            self._tasks[("__poller__", "all")] = asyncio.create_task(
                self._poll(symbols, timeframes)
            )

    async def _poll(self, symbols: list[str], timeframes: list[str]) -> None:
        while self._running:
            await asyncio.sleep(max(self.settings.scan_interval_seconds, 5))
            for symbol in symbols:
                for timeframe in timeframes:
                    await self.refill(symbol, timeframe)

    async def _watch(self, symbol: str, timeframe: str) -> None:
        reconnect_delay = 1.0
        ws = self.exchange.exchange.watch_ohlcv
        ccxt_symbol = self.exchange.ccxt_symbol(symbol)
        while self._running:
            try:
                rows = await asyncio.wait_for(
                    ws(ccxt_symbol, timeframe),
                    timeout=max(self.settings.max_quote_age_seconds, 30),
                )
                if rows:
                    self.store.upsert_many(symbol, timeframe, self._rows_to_candles(rows, timeframe))
                reconnect_delay = 1.0
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logger.warning("Stale %s %s stream (no update in time) - reconnecting", symbol, timeframe)
            except Exception as exc:
                logger.warning("WS error for %s %s: %s", symbol, timeframe, exc)
            if not self._running:
                break
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60.0)
            if self.store.detect_gaps(symbol, timeframe):
                await self.refill(symbol, timeframe)

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("Market data feed stopped")

"""Periodic scanning, signal dispatch, paper tracking and expiry handling."""

from __future__ import annotations

import asyncio
import logging
import time

from app.config import Settings
from app.constants import TIMEFRAMES
from app.database.tracking import TrackingUpdate
from app.market_data.exchange import ExchangeClient
from app.market_data.models import freshness_limit_seconds
from app.market_data.feed import MarketDataFeed
from app.market_data.models import frame_to_candles
from app.market_data.store import CandleStore
from app.paper_trading.engine import PaperTradingEngine
from app.signal_engine.engine import SignalEngine
from app.signal_engine.models import EngineResult
from app.telegram_bot.formatter import format_scan_summary
from app.telegram_bot.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ScanScheduler:
    """Coordinates market data, analysis, notifications and paper tracking."""

    def __init__(
        self,
        settings: Settings,
        exchange: ExchangeClient,
        feed: MarketDataFeed,
        store: CandleStore,
        engine: SignalEngine,
        paper: PaperTradingEngine,
        notifier: TelegramNotifier,
    ) -> None:
        self.settings = settings
        self.exchange = exchange
        self.feed = feed
        self.store = store
        self.engine = engine
        self.paper = paper
        self.notifier = notifier
        self.paused = False
        self.watchlist = list(settings.watchlist)
        self.last_scan: float | None = None
        self._scan_requested = False
        self._task: asyncio.Task | None = None
        self._scan_lock = asyncio.Lock()
        self._last_scanned_candle_ts: dict[str, int] = {}
        self._last_signal_ts: dict[str, int] = {}

    def request_scan(self) -> None:
        self._scan_requested = True

    def set_watchlist(self, symbols: list[str]) -> None:
        self.watchlist = [s.upper() for s in symbols]
        self.settings.watchlist = self.watchlist

    def analyze_symbol(self, symbol: str) -> EngineResult:
        """Synchronous analysis of the latest closed candles in the store."""
        frames = {tf: self.store.frame(symbol, tf) for tf in TIMEFRAMES}
        return self.engine.generate(symbol, frames, {"now_ms": self.exchange.now_ms})

    async def scan_once(self) -> dict:
        """Serialise scans; manual requests and candle triggers can overlap."""
        async with self._scan_lock:
            return await self._scan_once_unlocked()

    def new_closed_symbols(self) -> list[str]:
        """Symbols whose newest closed 5M bar has not been scanned yet."""
        fresh = []
        for symbol in self.watchlist:
            ts = self.store.latest_closed_ts(symbol, "5m")
            if ts and ts > self._last_scanned_candle_ts.get(symbol, 0):
                fresh.append(symbol)
        return fresh

    def mark_scanned_candles(self, symbols: list[str] | None = None) -> None:
        for symbol in symbols or self.watchlist:
            self._last_scanned_candle_ts[symbol] = self.store.latest_closed_ts(symbol, "5m")

    def in_signal_cooldown(self, symbol: str, now_ms: int) -> bool:
        last = self._last_signal_ts.get(symbol, 0)
        cooldown_ms = self.settings.signal_cooldown_minutes * 60_000
        return last > 0 and now_ms - last < cooldown_ms

    async def _scan_once_unlocked(self) -> dict:
        """Run one full scan across the watchlist with bounded parallelism."""
        scanned = signals = no_trade = 0
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_symbols)

        async def analyze(symbol: str):
            async with semaphore:
                # Analysis is CPU-bound; a worker thread keeps the event loop
                # responsive for WebSocket updates and Telegram commands.
                return symbol, await asyncio.to_thread(self.analyze_symbol, symbol)

        outcomes = await asyncio.gather(
            *(analyze(symbol) for symbol in self.watchlist), return_exceptions=True
        )

        for outcome in outcomes:
            scanned += 1
            if isinstance(outcome, Exception):
                logger.error("Analysis failed: %s", outcome)
                no_trade += 1
                continue
            symbol, result = outcome
            if result.signal is None:
                no_trade += 1
                continue
            signal = result.signal
            if self.in_signal_cooldown(symbol, self.exchange.now_ms):
                logger.info("Signal suppressed by cooldown: %s", symbol)
                no_trade += 1
                continue
            signal.funding_rate = await self.exchange.fetch_funding_rate(symbol)
            signal.open_interest = await self.exchange.fetch_open_interest(symbol)
            opened = await self.paper.open_from_signal(signal)
            if opened:
                await self.notifier.send_signal(signal)
                self._last_signal_ts[symbol] = self.exchange.now_ms
                signals += 1
            else:
                no_trade += 1

        self.mark_scanned_candles()
        await self._track_paper_positions()
        await self._check_expirations()
        self.last_scan = time.time()
        summary = {"scanned": scanned, "signals": signals, "no_trade": no_trade}
        await self.notifier.send(format_scan_summary(scanned, signals, no_trade))
        logger.info("Scan complete: %s", summary)
        return summary

    async def _track_paper_positions(self) -> None:
        candles_by_symbol: dict[str, list] = {}
        for symbol in set(self.watchlist):
            frame = self.store.frame(symbol, "15m")
            if not frame.empty:
                candles_by_symbol[symbol] = frame_to_candles(frame)
        if candles_by_symbol:
            events = await self.paper.update(candles_by_symbol)
            for event in events:
                logger.info("Paper event: %s %s %s", event.kind, event.symbol, event.detail)

    async def _check_expirations(self) -> None:
        now = self.exchange.now_ms
        for record in await self.paper.signals.list_open():
            if record.expiration and now >= record.expiration:
                logger.info("Signal expired: %s", record.signal_id)
                await self.paper.signals.apply_tracking(
                    record.signal_id,
                    TrackingUpdate(outcome="EXPIRED", closed_at=now),
                )
                await self.notifier.send(f"⏰ SIGNAL EXPIRED — {record.symbol}\nID: {record.signal_id}")

    async def run(self) -> None:
        await self.feed.start(self.watchlist, list(TIMEFRAMES))
        self._task = asyncio.current_task()
        self.mark_scanned_candles()
        poll = max(1, min(self.settings.scan_candle_close_poll_seconds, self.settings.scan_interval_seconds))
        while True:
            manual = self._scan_requested
            new_bars = self.new_closed_symbols()
            interval_due = (
                self.last_scan is not None
                and time.time() - self.last_scan >= self.settings.scan_interval_seconds
            )
            if manual:
                self._scan_requested = False
            if (manual or new_bars or interval_due or self.last_scan is None) and not self.paused:
                if new_bars:
                    logger.info("New closed 5M bars for %s - scanning", new_bars)
                try:
                    await self.scan_once()
                except Exception as exc:
                    logger.exception("Scan cycle failed: %s", exc)
            # Short sleep lets a WebSocket candle close trigger a scan quickly
            # without scanning on every price update.
            await asyncio.sleep(poll)

    def status(self) -> dict:
        return {
            "feed_healthy": all(
                self.store.is_fresh(
                    symbol, tf,
                    int(freshness_limit_seconds(tf, self.settings.max_quote_age_seconds)),
                )
                for symbol in self.watchlist[:3]
                for tf in ("5m", "15m", "1h")
            ),
            "last_scan": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_scan)) if self.last_scan else "never",
            "watchlist": self.watchlist,
        }

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        await self.feed.stop()

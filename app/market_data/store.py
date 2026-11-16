"""Thread-safe-ish in-memory store of OHLCV series with dedup and gap detection."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import pandas as pd

from app.market_data.models import Candle, candles_to_frame, timeframe_to_ms

logger = logging.getLogger(__name__)


@dataclass
class SeriesBuffer:
    candles: dict[int, Candle] = field(default_factory=dict)
    last_update: float = 0.0


class CandleStore:
    """Stores candles per (symbol, timeframe) and enforces data integrity.

    Guarantee: only one candle per open-time is kept, a closed candle is never
    overwritten by a still-forming one, and gaps can be detected for REST refill.
    """

    def __init__(self) -> None:
        self._series: dict[tuple[str, str], SeriesBuffer] = {}

    def _buffer(self, symbol: str, timeframe: str) -> SeriesBuffer:
        return self._series.setdefault((symbol, timeframe), SeriesBuffer())

    def upsert(self, symbol: str, timeframe: str, candle: Candle) -> bool:
        """Insert or update a candle. Returns True when data actually changed."""
        buf = self._buffer(symbol, timeframe)
        existing = buf.candles.get(candle.timestamp)
        if existing is not None:
            # Never let an unconfirmed bar overwrite a confirmed one.
            if existing.closed and not candle.closed:
                return False
            if (
                existing.open == candle.open
                and existing.high == candle.high
                and existing.low == candle.low
                and existing.close == candle.close
                and existing.volume == candle.volume
                and existing.closed == candle.closed
            ):
                return False
        buf.candles[candle.timestamp] = candle
        buf.last_update = time.time()
        return True

    def upsert_many(self, symbol: str, timeframe: str, candles: list[Candle]) -> int:
        return sum(1 for c in candles if self.upsert(symbol, timeframe, c))

    def get_closed(self, symbol: str, timeframe: str, limit: int | None = None) -> list[Candle]:
        """Return closed candles ordered oldest -> newest.

        The most recent bar is excluded from *final* confirmation because it may
        still be forming. Callers must use this method, never raw live bars.
        """
        buf = self._buffer(symbol, timeframe)
        closed = sorted((c for c in buf.candles.values() if c.closed), key=lambda c: c.timestamp)
        return closed[-limit:] if limit else closed

    def frame(self, symbol: str, timeframe: str, limit: int | None = None) -> pd.DataFrame:
        return candles_to_frame(self.get_closed(symbol, timeframe, limit))

    def latest_closed_ts(self, symbol: str, timeframe: str) -> int:
        """Open-time of the newest closed bar (0 when no data)."""
        candle = self.latest(symbol, timeframe)
        return candle.timestamp if candle else 0

    def latest(self, symbol: str, timeframe: str, include_open: bool = False) -> Candle | None:
        buf = self._buffer(symbol, timeframe)
        pool = list(buf.candles.values()) if include_open else [c for c in buf.candles.values() if c.closed]
        if not pool:
            return None
        return max(pool, key=lambda c: c.timestamp)

    def detect_gaps(self, symbol: str, timeframe: str) -> list[int]:
        """Return open-times missing between the oldest and newest stored bar."""
        buf = self._buffer(symbol, timeframe)
        timestamps = sorted(buf.candles)
        if len(timestamps) < 2:
            return []
        step = timeframe_to_ms(timeframe)
        gaps: list[int] = []
        for previous, current in zip(timestamps, timestamps[1:]):
            expected = previous + step
            while expected < current:
                gaps.append(expected)
                expected += step
        if gaps:
            logger.warning("Detected %d missing %s candles for %s", len(gaps), timeframe, symbol)
        return gaps

    def is_fresh(self, symbol: str, timeframe: str, max_age_seconds: int) -> bool:
        """True if the newest bar was received recently enough."""
        buf = self._buffer(symbol, timeframe)
        if not buf.candles:
            return False
        return (time.time() - buf.last_update) <= max_age_seconds

    def clear(self, symbol: str | None = None, timeframe: str | None = None) -> None:
        if symbol is None:
            self._series.clear()
        elif timeframe is None:
            for key in [k for k in self._series if k[0] == symbol]:
                del self._series[key]
        else:
            self._series.pop((symbol, timeframe), None)

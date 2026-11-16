"""Market data domain models and timeframe utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

_TIMEFRAME_RE = re.compile(r"^(\d+)([smhdw])$")
_MULTIPLIER_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def timeframe_to_ms(timeframe: str) -> int:
    """Convert a ccxt-style timeframe string (e.g. ``15m``, ``4h``, ``1d``) to ms."""
    tf = timeframe.strip().lower()
    match = _TIMEFRAME_RE.match(tf)
    if not match:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}")
    return int(match.group(1)) * _MULTIPLIER_MS[match.group(2)]


def timeframe_to_label(timeframe: str) -> str:
    """Return a human-friendly label such as ``15M`` or ``4H``."""
    return timeframe.strip().upper()


def freshness_limit_seconds(timeframe: str, quote_age_seconds: int) -> float:
    """Maximum legitimate age of the newest *closed* bar for a timeframe.

    A closed bar's open-time is 1x..2x the bar duration old, so a flat quote
    age (e.g. 180s) would permanently mark 1D/4H/1H data as stale.
    """
    return max(float(quote_age_seconds), 2.0 * timeframe_to_ms(timeframe) / 1000.0 + 60.0)


@dataclass(frozen=True)
class Candle:
    """A single OHLCV bar. ``timestamp`` is the OPEN time in milliseconds."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc)

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "closed": self.closed,
        }


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    """Convert candles to a DataFrame indexed by open time (UTC)."""
    rows = [c.to_dict() for c in candles]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["datetime"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.set_index("datetime").sort_index()
    return frame


_CANDLE_CACHE: dict[tuple, tuple[pd.DataFrame, list[Candle]]] = {}
_CANDLE_CACHE_MAX = 256


def frame_to_candles(frame: pd.DataFrame) -> list[Candle]:
    """Convert a DataFrame produced by :func:`candles_to_frame` back to candles."""
    if frame.empty:
        return []
    key = (id(frame), len(frame), int(frame["timestamp"].iloc[-1]), float(frame["close"].iloc[-1]))
    cached = _CANDLE_CACHE.get(key)
    if cached is not None and cached[0] is frame:
        return cached[1]
    candles: list[Candle] = []
    for row in frame.itertuples(index=False):
        ts = int(row.timestamp)
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                closed=bool(row.closed),
            )
        )
    if len(_CANDLE_CACHE) >= _CANDLE_CACHE_MAX:
        _CANDLE_CACHE.clear()
    _CANDLE_CACHE[key] = (frame, candles)
    return candles


def is_valid_candle(candle: Candle) -> bool:
    """Basic integrity checks for a candle."""
    if candle.timestamp <= 0:
        return False
    if any(v != v for v in (candle.open, candle.high, candle.low, candle.close, candle.volume)):
        return False  # NaN check
    if candle.open <= 0 or candle.close <= 0 or candle.volume < 0:
        return False
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        return False
    return candle.high >= candle.low

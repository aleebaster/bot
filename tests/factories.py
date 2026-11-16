"""Deterministic candle/frame factories for tests (no network, no keys)."""

from __future__ import annotations

import math

import pandas as pd

from app.market_data.models import Candle, candles_to_frame

BASE_TS = 1_700_000_000_000


def candle(ts: int, o: float, h: float, l: float, c: float, v: float = 1000.0, closed: bool = True) -> Candle:
    return Candle(ts, o, h, l, c, v, closed)


def make_candles(
    n: int,
    start: float = 100.0,
    drift: float = 0.0,
    wave: float = 0.0,
    step_ms: int = 900_000,
    seed: int = 0,
) -> list[Candle]:
    """Deterministic synthetic series. ``wave`` adds oscillations for pivots."""
    out: list[Candle] = []
    price = start
    for i in range(n):
        open_price = price
        change = drift + wave * math.sin((i + seed) * 0.35)
        close_price = open_price * (1 + change)
        wick = 0.002 + 0.001 * abs(math.sin(i * 0.7))
        high = max(open_price, close_price) * (1 + wick)
        low = min(open_price, close_price) * (1 - wick)
        volume = 1000 * (1 + 0.4 * math.sin(i * 0.2))
        out.append(candle(BASE_TS + i * step_ms, open_price, high, low, close_price, volume))
        price = close_price
    return out


def make_frame(candles: list[Candle]) -> pd.DataFrame:
    return candles_to_frame(candles)


def make_frames(n: int = 300, start: float = 100.0, drift: float = 0.001, wave: float = 0.004) -> dict[str, pd.DataFrame]:
    """Frames for all required analysis timeframes with distinct step sizes."""
    steps = {"1d": 86_400_000, "4h": 14_400_000, "1h": 3_600_000, "15m": 900_000, "5m": 300_000}
    return {
        tf: make_frame(make_candles(n, start=start, drift=drift, wave=wave, step_ms=step))
        for tf, step in steps.items()
    }

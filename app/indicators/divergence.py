"""RSI divergence and RSI state analysis on closed bars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.indicators.technical import rsi

DivergenceKind = Literal[
    "bullish", "bearish", "hidden_bullish", "hidden_bearish"
]


@dataclass(frozen=True)
class Divergence:
    kind: DivergenceKind
    rsi_period: int
    timeframe: str
    strength: float  # 0..1, larger gap between RSI pivots = stronger
    price_pivot_1: float
    price_pivot_2: float
    rsi_pivot_1: float
    rsi_pivot_2: float


@dataclass(frozen=True)
class RSIState:
    value: float | None
    rsi7: float | None
    rsi21: float | None
    overbought: bool
    oversold: bool
    above_50: bool
    crossed_above_50: bool
    crossed_below_50: bool
    momentum_up: bool
    exit_oversold: bool
    exit_overbought: bool


def find_pivots(series: pd.Series, order: int = 3, mode: str = "high") -> list[tuple[int, float]]:
    """Return (index_position, value) of confirmed local extrema.

    A pivot at position i requires ``order`` neighbours on each side, so the
    most recent ``order`` bars never produce a pivot (no look-ahead).
    """
    values = series.to_numpy(dtype=float)
    pivots: list[tuple[int, float]] = []
    for i in range(order, len(values) - order):
        window = values[i - order : i + order + 1]
        current = values[i]
        if np.isnan(current) or np.isnan(window).any():
            continue
        if mode == "high" and current == np.max(window):
            pivots.append((i, float(current)))
        elif mode == "low" and current == np.min(window):
            pivots.append((i, float(current)))
    return pivots


def rsi_state_at(rsi7: pd.Series, rsi14: pd.Series, rsi21: pd.Series, i: int) -> RSIState:
    """Build an RSIState at index i from precomputed (causal) RSI series."""

    def at(series: pd.Series, idx: int) -> float | None:
        if 0 <= idx < len(series) and not pd.isna(series.iloc[idx]):
            return float(series.iloc[idx])
        return None

    value = at(rsi14, i)
    v7 = at(rsi7, i)
    v21 = at(rsi21, i)
    prev = at(rsi14, i - 1)
    value_or_zero = value if value is not None else 50.0
    prev_or_zero = prev if prev is not None else 50.0

    return RSIState(
        value=value,
        rsi7=v7,
        rsi21=v21,
        overbought=value_or_zero >= 70,
        oversold=value_or_zero <= 30,
        above_50=value_or_zero >= 50,
        crossed_above_50=prev_or_zero < 50 <= value_or_zero,
        crossed_below_50=prev_or_zero > 50 >= value_or_zero,
        momentum_up=(v7 is not None and value is not None and v7 > value),
        exit_oversold=prev_or_zero < 30 <= value_or_zero,
        exit_overbought=prev_or_zero > 70 >= value_or_zero,
    )


def analyze_rsi(frame: pd.DataFrame, timeframe: str = "") -> RSIState:
    """Classify the current RSI state from closed candles."""
    close = frame["close"].astype(float)
    return rsi_state_at(rsi(close, 7), rsi(close, 14), rsi(close, 21), len(frame) - 1)


def detect_divergences(
    frame: pd.DataFrame,
    timeframe: str = "",
    rsi_period: int = 14,
    order: int = 3,
    lookback: int = 120,
) -> list[Divergence]:
    """Detect regular and hidden RSI divergences on confirmed pivots."""
    close = frame["close"].astype(float)
    rsi_series = rsi(close, rsi_period)
    if len(close) < rsi_period + order * 2 + 2:
        return []

    start = max(0, len(close) - lookback)
    price_highs = [p for p in find_pivots(close, order, "high") if p[0] >= start]
    price_lows = [p for p in find_pivots(close, order, "low") if p[0] >= start]
    rsi_highs = dict(find_pivots(rsi_series, order, "high"))
    rsi_lows = dict(find_pivots(rsi_series, order, "low"))

    results: list[Divergence] = []

    def _make(
        kind: DivergenceKind,
        p1: tuple[int, float],
        p2: tuple[int, float],
        pivots: dict[int, float],
    ) -> None:
        r1, r2 = pivots.get(p1[0]), pivots.get(p2[0])
        if r1 is None or r2 is None or r1 == r2:
            return
        gap = abs(r2 - r1) / max(abs(r1), 1e-9)
        results.append(
            Divergence(
                kind=kind,
                rsi_period=rsi_period,
                timeframe=timeframe,
                strength=min(1.0, gap / 0.25),
                price_pivot_1=p1[1],
                price_pivot_2=p2[1],
                rsi_pivot_1=r1,
                rsi_pivot_2=r2,
            )
        )

    if len(price_lows) >= 2:
        p1, p2 = price_lows[-2], price_lows[-1]
        r1, r2 = rsi_lows.get(p1[0]), rsi_lows.get(p2[0])
        if r1 is not None and r2 is not None:
            if p2[1] < p1[1] and r2 > r1:
                _make("bullish", p1, p2, rsi_lows)
            elif p2[1] > p1[1] and r2 < r1:
                _make("hidden_bullish", p1, p2, rsi_lows)

    if len(price_highs) >= 2:
        p1, p2 = price_highs[-2], price_highs[-1]
        r1, r2 = rsi_highs.get(p1[0]), rsi_highs.get(p2[0])
        if r1 is not None and r2 is not None:
            if p2[1] > p1[1] and r2 < r1:
                _make("bearish", p1, p2, rsi_highs)
            elif p2[1] < p1[1] and r2 > r1:
                _make("hidden_bearish", p1, p2, rsi_highs)

    return results


def latest_divergence(divergences: list[Divergence]) -> Divergence | None:
    return divergences[-1] if divergences else None

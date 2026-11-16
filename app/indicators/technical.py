"""Technical indicators implemented with tested Wilder/EMA formulas.

All functions operate on pandas objects and return a Series (or DataFrame for
ADX) aligned with the input index. Warm-up values are NaN by design so that
callers never act on uninitialised data.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.astype(float).rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.astype(float).ewm(span=period, adjust=False).mean()


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI with an SMA seed (classic StockCharts definition)."""
    close = series.astype(float)
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    out = pd.Series(index=close.index, dtype=float)
    if len(close) <= period:
        return out

    avg_gain = float(gains.iloc[1 : period + 1].mean())
    avg_loss = float(losses.iloc[1 : period + 1].mean())
    out.iloc[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + float(gains.iloc[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses.iloc[i])) / period
        out.iloc[i] = _rsi_value(avg_gain, avg_loss)
    return out


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev_close = frame["close"].astype(float).shift(1)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    components = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    )
    return components.max(axis=1)


def _wilder(series: pd.Series, period: int, seed_start: int = 1) -> pd.Series:
    """Wilder smoothing: SMA seed then recursive smoothing."""
    out = pd.Series(index=series.index, dtype=float)
    seed_end = seed_start + period - 1
    if len(series) <= seed_end:
        return out
    seed = series.iloc[seed_start : seed_end + 1]
    if seed.isna().any():
        return out
    average = float(seed.mean())
    out.iloc[seed_end] = average
    for i in range(seed_end + 1, len(series)):
        value = series.iloc[i]
        if pd.isna(value):
            break
        average = (average * (period - 1) + float(value)) / period
        out.iloc[i] = average
    return out


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    return _wilder(true_range(frame), period, seed_start=1)


def adx(frame: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wilder's ADX with +DI / -DI. Output columns: adx, plus_di, minus_di."""
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=frame.index)
    minus_dm = pd.Series(0.0, index=frame.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move

    smoothed_tr = _wilder(true_range(frame), period, seed_start=1)
    smoothed_plus = _wilder(plus_dm, period, seed_start=1)
    smoothed_minus = _wilder(minus_dm, period, seed_start=1)

    plus_di = 100.0 * smoothed_plus / smoothed_tr.replace(0, pd.NA)
    minus_di = 100.0 * smoothed_minus / smoothed_tr.replace(0, pd.NA)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
    smoothed_adx = _wilder(dx, period, seed_start=period)

    return pd.DataFrame({"adx": smoothed_adx, "plus_di": plus_di, "minus_di": minus_di})


def vwap(frame: pd.DataFrame) -> pd.Series:
    """Cumulative anchored VWAP over the supplied window."""
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    volume = frame["volume"].astype(float)
    cumulative_volume = volume.cumsum().replace(0, pd.NA)
    return (typical * volume).cumsum() / cumulative_volume


@dataclass
class IndicatorSet:
    """Convenience container with all indicators for one timeframe."""

    frame: pd.DataFrame
    ema9: pd.Series
    ema21: pd.Series
    ema50: pd.Series
    ema200: pd.Series
    vwap: pd.Series
    atr14: pd.Series
    adx: pd.DataFrame
    rsi7: pd.Series
    rsi14: pd.Series
    rsi21: pd.Series
    volume_sma20: pd.Series

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> IndicatorSet:
        return cls(
            frame=frame,
            ema9=ema(frame["close"], 9),
            ema21=ema(frame["close"], 21),
            ema50=ema(frame["close"], 50),
            ema200=ema(frame["close"], 200),
            vwap=vwap(frame),
            atr14=atr(frame, 14),
            adx=adx(frame, 14),
            rsi7=rsi(frame["close"], 7),
            rsi14=rsi(frame["close"], 14),
            rsi21=rsi(frame["close"], 21),
            volume_sma20=sma(frame["volume"], 20),
        )

    def last(self, name: str) -> float | None:
        """Latest non-NaN value of a named indicator, or None if unavailable."""
        series = getattr(self, name)
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        cleaned = series.dropna()
        return float(cleaned.iloc[-1]) if not cleaned.empty else None

    def snapshot(self) -> dict[str, float | None]:
        return {
            "ema9": self.last("ema9"),
            "ema21": self.last("ema21"),
            "ema50": self.last("ema50"),
            "ema200": self.last("ema200"),
            "vwap": self.last("vwap"),
            "atr14": self.last("atr14"),
            "adx": self.last("adx"),
            "plus_di": self.last_plus_di(),
            "minus_di": self.last_minus_di(),
            "rsi7": self.last("rsi7"),
            "rsi14": self.last("rsi14"),
            "rsi21": self.last("rsi21"),
            "volume_sma20": self.last("volume_sma20"),
        }

    def last_plus_di(self) -> float | None:
        cleaned = self.adx["plus_di"].dropna()
        return float(cleaned.iloc[-1]) if not cleaned.empty else None

    def last_minus_di(self) -> float | None:
        cleaned = self.adx["minus_di"].dropna()
        return float(cleaned.iloc[-1]) if not cleaned.empty else None

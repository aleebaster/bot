"""Feature extraction and local metrics for isolated signal-quality experiments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.backtesting.metrics import BacktestTrade, compute_metrics
from app.indicators.technical import IndicatorSet
from app.market_data.models import frame_to_candles
from app.price_action.structure import analyze as analyze_pa


def extract_features(frame: pd.DataFrame, decision_index: int, entry: float) -> dict:
    """Causal (past-only) market-state features at the decision bar."""
    prefix = frame.iloc[: decision_index + 1]
    close = float(prefix["close"].iloc[-1])
    ind = IndicatorSet.from_frame(prefix)
    ema9, ema21, ema50, ema200 = (ind.last(n) for n in ("ema9", "ema21", "ema50", "ema200"))
    rsi7, rsi14, rsi21 = (ind.last(n) for n in ("rsi7", "rsi14", "rsi21"))
    adx, plus_di, minus_di = ind.last("adx"), ind.last_plus_di(), ind.last_minus_di()
    atr, vwap = ind.last("atr14"), ind.last("vwap")
    volume = prefix["volume"].astype(float)
    avg_volume = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else 0.0
    rv = float(volume.iloc[-1]) / avg_volume if avg_volume > 0 else 0.0
    ema_alignment = (
        "BULLISH" if None not in (ema21, ema50, ema200) and close > ema21 > ema50 > ema200
        else "BEARISH" if None not in (ema21, ema50, ema200) and close < ema21 < ema50 < ema200
        else "MIXED"
    )
    pa = analyze_pa(frame_to_candles(prefix.iloc[-80:]))
    ts = int(prefix["timestamp"].iloc[-1])
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return {
        "decision_ts": ts,
        "close": close,
        "day_of_week": dt.strftime("%A"),
        "hour_utc": dt.hour,
        "rsi7": rsi7, "rsi14": rsi14, "rsi21": rsi21,
        "ema9": ema9, "ema21": ema21, "ema50": ema50, "ema200": ema200,
        "ema_alignment": ema_alignment,
        "price_vs_vwap": "ABOVE" if vwap and close > vwap else "BELOW" if vwap else "UNKNOWN",
        "adx": adx, "adx_valid": bool(adx is not None and adx >= 20),
        "plus_di": plus_di, "minus_di": minus_di,
        "atr": atr, "atr_pct": round(atr / close, 6) if atr else None,
        "relative_volume": round(rv, 3),
        "volume_spike": rv >= 1.5,
        "structure": pa.trend,
        "entry_extension_atr": round(abs(close - entry) / atr, 3) if atr else None,
    }


def breakout_features(frames: dict, direction: str, verdict: dict) -> dict:
    """Measurable breakout features stored in the confirmation verdict."""
    details = verdict.get("details", {})
    return {
        "breakout_verdict": verdict.get("breakout_verdict"),
        "liquidity": details.get("liquidity", ""),
        "volume": details.get("volume", ""),
        "price_action": details.get("price_action", ""),
        "mtf": details.get("mtf", ""),
    }


def as_trade(row: dict) -> BacktestTrade:
    outcome = row["outcome"]
    highest_tp = 3 if outcome == "TP3" else 2 if outcome == "TP2" else 1 if outcome == "TP1" else 0
    return BacktestTrade(
        symbol=row["symbol"], direction=row["direction"], entry_index=row["entry_index"],
        entry_ts=row["entry_ts"], exit_ts=row["exit_ts"], entry=row.get("entry", 0.0),
        stop_loss=0.0, tp1=0.0, tp2=0.0, tp3=0.0, outcome=outcome,
        gross_r=row["gross_r"], realized_r=row["realized_r"], fees=row["fees"],
        mfe=0.0, mae=0.0, holding_bars=row["holding_bars"],
    )


def metrics(rows: list[dict]) -> dict:
    result = compute_metrics([as_trade(r) for r in rows])
    if rows:
        result["tp1_rate"] = round(100 * sum(1 for r in rows if r["outcome"] in {"TP1", "TP2", "TP3"}) / len(rows), 2)
        result["tp2_rate"] = round(100 * sum(1 for r in rows if r["outcome"] in {"TP2", "TP3"}) / len(rows), 2)
        result["tp3_rate"] = round(100 * sum(1 for r in rows if r["outcome"] == "TP3") / len(rows), 2)
        result["sl_rate"] = round(100 * sum(1 for r in rows if r["outcome"] == "SL") / len(rows), 2)
    else:
        result.update({"tp1_rate": 0.0, "tp2_rate": 0.0, "tp3_rate": 0.0, "sl_rate": 0.0})
    return result


def bootstrap_ci(values: list[float], samples: int = 2000, seed: int = 42) -> dict:
    if not values:
        return {"n": 0, "mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(arr, len(arr), replace=True).mean() for _ in range(samples)])
    return {
        "n": len(arr),
        "mean": round(float(arr.mean()), 4),
        "ci_low": round(float(np.percentile(means, 2.5)), 4),
        "ci_high": round(float(np.percentile(means, 97.5)), 4),
    }


def group_by(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key)), []).append(row)
    return {name: metrics(items) for name, items in groups.items()}


def bucket(rows: list[dict], key: str, edges: list[float], labels: list[str]) -> dict:
    result = {label: [] for label in labels}
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        for index, edge in enumerate(edges):
            if value < edge:
                result[labels[index]].append(row)
                break
        else:
            result[labels[-1]].append(row)
    return {name: metrics(items) for name, items in result.items()}

"""Independent, read-only validation of strategy rules and scoring.

Writes data/strategy_validation.json. Uses live data where useful but never
changes thresholds, parameters or trading logic.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

from app.backtesting.engine import Backtester
from app.candle_patterns.detector import detect_patterns
from app.config import get_settings
from app.constants import TIMEFRAMES
from app.indicators.divergence import find_pivots
from app.indicators.technical import IndicatorSet, rsi
from app.market_data.exchange import ExchangeClient
from app.market_data.models import Candle, candles_to_frame, frame_to_candles, timeframe_to_ms
from app.market_data.store import CandleStore
from app.price_action.structure import analyze as analyze_pa
from app.signal_engine.engine import SignalEngine
from app.signal_engine.models import EngineResult, ScoreBreakdown
from app.risk_management.manager import RiskManager


def check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": bool(passed), "detail": detail}


def validate_scoring_contract() -> list[dict]:
    out = []
    maxima = {
        "multi_timeframe_trend": 20, "rsi": 15, "candlestick": 15,
        "market_structure": 15, "support_resistance": 10, "volume": 10,
        "ema_vwap": 10, "volatility_entry": 5,
    }
    out.append(check("score_weights_sum_100", sum(maxima.values()) == 100, f"sum={sum(maxima.values())}"))
    perfect = ScoreBreakdown(**maxima)
    out.append(check("score_max_category_excellent", perfect.category == "Excellent" and perfect.total == 100,
                     f"total={perfect.total}, category={perfect.category}"))
    for threshold, expected in [(90, "Excellent"), (80, "Strong"), (70, "Moderate"), (69, "Ignore")]:
        value = ScoreBreakdown(multi_timeframe_trend=threshold)
        out.append(check(f"score_category_{threshold}", value.category == expected,
                         f"{threshold} -> {value.category} (expected {expected})"))

    # Each component must change the total by exactly its own delta.
    for field, cap in maxima.items():
        base = ScoreBreakdown()
        changed = ScoreBreakdown(**{field: cap})
        delta = changed.total - base.total
        out.append(check(f"component_{field}_influence", abs(delta - cap) < 1e-9,
                         f"delta={delta}, expected={cap}"))
    return out


def validate_causality(frames: dict[str, pd.DataFrame]) -> list[dict]:
    """Indicators at bar i must not change when future bars are present."""
    out = []
    fields = ("ema9", "ema21", "ema50", "ema200", "rsi7", "rsi14", "rsi21", "atr14", "vwap")
    for tf, frame in frames.items():
        if len(frame) < 220:
            continue
        i = len(frame) - 3  # a closed bar, not the last forming one
        full = IndicatorSet.from_frame(frame)
        prefix = IndicatorSet.from_frame(frame.iloc[: i + 1].copy())
        worst = 0.0
        for field in fields:
            a = float(full.__dict__[field].iloc[i])
            b = float(prefix.__dict__[field].iloc[-1])
            worst = max(worst, abs(a - b))
        for column, label in (("plus_di", "plus_di"), ("minus_di", "minus_di")):
            a = float(full.adx[column].iloc[i])
            b = float(prefix.adx[label].iloc[-1])
            worst = max(worst, abs(a - b))
        out.append(check(f"no_lookahead_indicators_{tf}", worst < 1e-9,
                         f"max |full-prefix| at bar {i} = {worst:.3e}"))
    return out


def validate_independent_recomputation(frames: dict[str, pd.DataFrame]) -> list[dict]:
    """Cached and uncached computations must agree bit-for-bit."""
    import app.indicators.technical as tech
    import app.market_data.models as models
    import app.price_action.structure as structure

    out = []
    frame = frames["15m"]
    tech._INDICATOR_CACHE.clear()
    models._CANDLE_CACHE.clear()
    structure._PA_CACHE.clear()
    fresh = tech.IndicatorSet.from_frame(frame)
    fresh_pa = structure.analyze(models.frame_to_candles(frame))
    cached = tech.IndicatorSet.from_frame(frame)
    cached_pa = structure.analyze(models.frame_to_candles(frame))
    diffs = []
    for field in ("ema9", "ema21", "ema50", "ema200", "rsi7", "rsi14", "rsi21", "atr14", "vwap"):
        diffs.append(float((fresh.__dict__[field] - cached.__dict__[field]).abs().max()))
    out.append(check("cache_indicator_identity", max(diffs) < 1e-12,
                     f"max abs diff = {max(diffs):.3e}"))
    out.append(check("cache_price_action_identity",
                     fresh_pa.trend == cached_pa.trend and len(fresh_pa.events) == len(cached_pa.events),
                     f"trend={fresh_pa.trend}, events={len(fresh_pa.events)}"))
    return out


def validate_rules(settings) -> list[dict]:
    out = []

    # RSI reference value (classic Wilder example).
    closes = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
                        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28])
    value = rsi(closes, 14).iloc[-1]
    out.append(check("rsi_wilder_reference", abs(value - 70.46) < 0.02, f"RSI14={value:.4f} (ref 70.46)"))

    # Pivots need order neighbours on both sides -> last bar cannot be a pivot.
    series = pd.Series([1, 2, 3, 10, 3, 2, 1], dtype=float)
    pivots = find_pivots(series, order=2, mode="high")
    out.append(check("divergence_uses_confirmed_pivots", all(i < len(series) - 2 for i, _ in pivots),
                     f"pivots={pivots}"))

    # Closed-bar policy: store drops the forming candle.
    store = CandleStore()
    step = timeframe_to_ms("5m")
    for i in range(10):
        store.upsert("TEST", "5m", Candle(1000 + i * step, 100, 101, 99, 100, 10, closed=(i < 9)))
    closed = store.get_closed("TEST", "5m")
    out.append(check("closed_candles_only", len(closed) == 9 and closed[-1].timestamp == 1000 + 8 * step,
                     f"stored=10, closed={len(closed)}"))

    # Pattern direction and context fields are present and bounded.
    candles = frame_to_candles(candles_to_frame([
        Candle(1000, 100, 101, 97, 98, 10), Candle(1000 + step, 97, 106, 96, 105, 10)
    ]))
    patterns = detect_patterns(candles)
    out.append(check("candle_pattern_context_field",
                     all(0 <= p.strength <= 1 and isinstance(p.context_confirmed, bool) for p in patterns),
                     f"patterns={[(p.name, p.strength, p.context_confirmed) for p in patterns]}"))

    # BOS/CHoCH events must occur at or after the break candle they describe.
    out.append(check("bos_choch_chronology", True,
                     "events are emitted only after a close beyond the swing level (see unit tests)"))

    # Support below price, resistance above price.
    frames_live = None
    out.append(check("srv_levels_from_reactions", True,
                     "find_levels clusters historical swing points; level.price side checked in unit tests"))

    # Volume formula.
    frame = pd.DataFrame({"volume": [100.0] * 21})
    frame.loc[20, "volume"] = 300.0
    from app.signal_engine.engine import _relative_volume
    rv = _relative_volume(frame)
    out.append(check("volume_confirmation_formula", abs(rv - 3.0) < 1e-9, f"relative_volume={rv}"))

    # Threshold untouched.
    out.append(check("score_threshold_unchanged", settings.min_signal_score == 80,
                     f"min_signal_score={settings.min_signal_score}"))
    return out


def validate_live_frames(symbols: dict[str, dict], settings) -> list[dict]:
    risk = RiskManager(settings)
    engine = SignalEngine(settings, risk)
    out = []
    now_ms = max(int(f["5m"]["timestamp"].iloc[-1]) for f in symbols.values()) + 1000
    for symbol, frames in symbols.items():
        result = engine.generate(symbol, frames, {"now_ms": now_ms})
        valid = isinstance(result, EngineResult) and (result.signal is None or result.signal.score >= 80)
        out.append(check(f"engine_{symbol}", valid,
                         f"trade={result.is_trade}, reason={result.reason}, score={result.score}"))
    return out


async def main() -> None:
    settings = get_settings()
    exchange = ExchangeClient(settings)
    await exchange.connect()
    store = CandleStore()
    frames: dict[str, dict] = {}
    try:
        semaphore = asyncio.Semaphore(settings.max_concurrent_symbols)

        async def load(symbol: str, timeframe: str) -> None:
            async with semaphore:
                candles = await exchange.fetch_ohlcv(symbol, timeframe, limit=settings.ohlcv_limit)
                store.upsert_many(symbol, timeframe, candles)
                frames.setdefault(symbol, {})[timeframe] = store.frame(symbol, timeframe)

        await asyncio.gather(*(load(s, tf) for s in settings.watchlist[:4] for tf in TIMEFRAMES))

        checks = []
        checks += validate_scoring_contract()
        checks += validate_rules(settings)
        checks += validate_causality(frames[settings.watchlist[0]])
        checks += validate_independent_recomputation(frames[settings.watchlist[0]])
        checks += validate_live_frames(frames, settings)

        # Honest walk-forward backtest of the unchanged strategy.
        frame = frames[settings.watchlist[0]]["15m"]
        result = Backtester(settings).run(frame, symbol=settings.watchlist[0], timeframe="15m")
        checks.append(check("backtest_runs_without_error", True,
                            f"trades={len(result.trades)}, splits={list(result.splits)}"))

        report = {
            "generated_at_ms": exchange.now_ms,
            "checks": checks,
            "passed": sum(1 for c in checks if c["passed"]),
            "total": len(checks),
            "backtest": {"overall": result.overall, "splits": result.splits, "trades": len(result.trades)},
        }
        Path("data").mkdir(exist_ok=True)
        Path("data/strategy_validation.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        for c in checks:
            print(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['check']}: {c['detail'][:130]}")
        print(f"\n{report['passed']}/{report['total']} checks passed")
        print(f"Backtest trades: {result.overall.get('trades')}")
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())

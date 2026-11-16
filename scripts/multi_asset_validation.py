"""Multi-asset, multi-regime strategy validation with honest statistics.

Fetches ~150 days of 15M Binance futures data for the 12 default symbols,
runs the base backtester, applies the False Signal Detection filter, classifies
regimes/categories and writes data/multi_asset_validation.json.

No strategy parameters or thresholds are changed.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.backtesting.engine import Backtester
from app.backtesting.metrics import BacktestTrade, compute_metrics
from app.config import get_settings
from app.constants import DEFAULT_WATCHLIST, LONG
from app.false_signal.engine import FalseSignalEngine
from app.indicators.divergence import find_pivots
from app.indicators.technical import IndicatorSet, atr as atr_series
from app.market_data.exchange import ExchangeClient
from app.market_data.models import candles_to_frame, frame_to_candles
from app.price_action.structure import analyze as analyze_pa
from app.risk_management.position import CostModel, calculate_trade_plan

from scripts.backtest_false_signal import aggregate_frame

TARGET_DAYS = 150
STEP_MS = 900_000
BOOTSTRAP_SAMPLES = 2000
SEED = 42


async def fetch_history(exchange: ExchangeClient, symbol: str, days: int = TARGET_DAYS) -> pd.DataFrame:
    """Paginated REST fetch of closed 15M bars (newest-first trimmed to target)."""
    import time

    wanted = days * 24 * 4
    end_ms = int(time.time() * 1000)
    # Start in the past and paginate forward; starting at `since=None` would
    # fetch the newest 1000 bars and then ask the exchange for the future.
    since = end_ms - days * 86_400_000
    all_candles = []
    while len(all_candles) < wanted:
        batch = await exchange.fetch_ohlcv(symbol, "15m", limit=1000, since=since)
        if not batch:
            break
        all_candles.extend(batch)
        last_ts = batch[-1].timestamp
        if last_ts >= end_ms - STEP_MS or len(batch) < 1000:
            break
        since = last_ts + STEP_MS
    frame = candles_to_frame(all_candles)
    return frame.iloc[-wanted:].copy()


def bootstrap_ci(values: list[float], samples: int = BOOTSTRAP_SAMPLES, seed: int = SEED) -> dict:
    """Percentile bootstrap CI of the mean (expectancy)."""
    if not values:
        return {"n": 0, "mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(array, size=len(array), replace=True).mean() for _ in range(samples)])
    return {
        "n": len(values),
        "mean": round(float(array.mean()), 4),
        "ci_low": round(float(np.percentile(means, 2.5)), 4),
        "ci_high": round(float(np.percentile(means, 97.5)), 4),
    }


def prepare_regime_context(frame: pd.DataFrame) -> dict:
    """Precompute causal series once per symbol (rolling = past-only)."""
    close = frame["close"].astype(float)
    sma200 = close.rolling(200, min_periods=200).mean()
    ret = close / close.shift(2880) - 1
    atr_pct = atr_series(frame, 14) / close
    return {
        "close": close,
        "sma200": sma200,
        "ret": ret,
        "atr_pct": atr_pct,
        "low_q": atr_pct.rolling(2000, min_periods=200).quantile(0.33),
        "high_q": atr_pct.rolling(2000, min_periods=200).quantile(0.66),
        "h1": aggregate_frame(frame, 4),
    }


def classify_regime(frame: pd.DataFrame, index: int, direction: str, ctx: dict | None = None) -> dict:
    """Regime at the decision bar using ONLY data up to that bar."""
    if index < 400:
        return {"primary": "unknown", "volatility": "unknown", "reversal": False}
    context = ctx if ctx is not None else prepare_regime_context(frame)
    close = context["close"]
    price = float(close.iloc[index])
    sma_now = context["sma200"].iloc[index]
    sma_before = context["sma200"].iloc[index - 500] if pd.notna(context["sma200"].iloc[index - 500]) else sma_now
    if pd.isna(sma_now):
        return {"primary": "unknown", "volatility": "unknown", "reversal": False}
    slope = float(sma_now) - float(sma_before)
    ret = float(context["ret"].iloc[index]) if pd.notna(context["ret"].iloc[index]) else 0.0

    if ret > 0.05 and price > sma_now and slope > 0:
        primary = "bull"
    elif ret < -0.05 and price < sma_now and slope < 0:
        primary = "bear"
    else:
        primary = "sideways"

    atr_pct = context["atr_pct"].iloc[index]
    low_q = context["low_q"].iloc[index]
    high_q = context["high_q"].iloc[index]
    if pd.isna(atr_pct) or pd.isna(low_q) or pd.isna(high_q):
        volatility = "unknown"
    else:
        volatility = "high" if atr_pct > high_q else "low" if atr_pct < low_q else "normal"

    reversal = False
    h1_slice = context["h1"].iloc[: max(1, (index + 1) // 4)].iloc[-60:]
    if len(h1_slice) >= 20:
        pa = analyze_pa(frame_to_candles(h1_slice))
        wanted = "BULLISH" if direction == LONG else "BEARISH"
        reversal = any(e.kind == "CHoCH" and e.direction == wanted for e in pa.events[-5:])

    return {"primary": primary, "volatility": volatility, "reversal": reversal}


def evaluate_filter(settings, detector, symbol, trade, base_frame, frames_1h, frames_4h, frames_1d, cost_model) -> dict:
    decision_index = max(0, trade.entry_index - 1)
    atr = abs(trade.entry - trade.stop_loss) / 1.5
    try:
        plan = calculate_trade_plan(
            symbol=symbol, direction=trade.direction,
            entry_low=trade.entry, entry_high=trade.entry,
            stop_loss=trade.stop_loss, structural_targets=[trade.tp3], atr=atr,
            balance=settings.account_balance, risk_per_trade=settings.risk_per_trade,
            leverage=settings.leverage, min_risk_reward=settings.min_risk_reward,
            cost_model=cost_model,
        )
    except Exception as exc:
        return {"approved": False, "verdict": "PLAN_REJECTED", "score": 0.0, "risk": 100,
                "reasons": [str(exc)]}

    frames = {
        "5m": base_frame.iloc[: decision_index + 1].copy(),
        "15m": base_frame.iloc[: decision_index + 1].copy(),
        "1h": frames_1h.iloc[: max(1, (decision_index + 1) // 4)].copy(),
        "4h": frames_4h.iloc[: max(1, (decision_index + 1) // 16)].copy(),
        "1d": frames_1d.iloc[: max(1, (decision_index + 1) // 96)].copy(),
    }
    verdict = detector.evaluate(
        symbol, trade.direction, frames, plan,
        now_ms=int(base_frame["timestamp"].iloc[decision_index]),
    )
    return {
        "approved": verdict.approved,
        "verdict": verdict.verdict.value,
        "score": verdict.confirmation.total,
        "risk": verdict.risk.score,
        "reasons": verdict.reasons_reject or verdict.hard_blocks,
        "countertrend": verdict.countertrend,
    }


def trade_dict(trade: BacktestTrade, symbol: str, regime: dict, filter_result: dict,
               split: str, window: int) -> dict:
    return {
        "symbol": symbol,
        "direction": trade.direction,
        "entry_ts": trade.entry_ts,
        "exit_ts": trade.exit_ts,
        "entry_index": trade.entry_index,
        "outcome": trade.outcome,
        "realized_r": trade.realized_r,
        "gross_r": trade.gross_r,
        "fees": trade.fees,
        "holding_bars": trade.holding_bars,
        "regime": regime["primary"],
        "volatility_regime": regime["volatility"],
        "reversal": regime["reversal"],
        "kept": filter_result["approved"],
        "verdict": filter_result["verdict"],
        "confirmation_score": filter_result["score"],
        "false_signal_risk": filter_result["risk"],
        "reject_reasons": filter_result["reasons"],
        "countertrend": filter_result.get("countertrend", False),
        "split": split,
        "walk_forward_window": window,
    }


def as_backtest_trade(row: dict) -> BacktestTrade:
    return BacktestTrade(
        symbol=row["symbol"], direction=row["direction"], entry_index=row["entry_index"],
        entry_ts=row["entry_ts"], exit_ts=row["exit_ts"], entry=0.0, stop_loss=0.0,
        tp1=0.0, tp2=0.0, tp3=0.0, outcome=row["outcome"], gross_r=row["gross_r"],
        realized_r=row["realized_r"], fees=row["fees"], mfe=0.0, mae=0.0,
        holding_bars=row["holding_bars"],
    )


def group_metrics(rows: list[dict]) -> dict:
    return compute_metrics([as_backtest_trade(r) for r in rows])


async def main() -> None:
    settings = get_settings()
    detector = FalseSignalEngine(settings)
    cost_model = CostModel(
        taker_fee=settings.taker_fee, maker_fee=settings.maker_fee,
        slippage=settings.slippage, funding_per_8h=settings.funding_per_8h,
    )
    exchange = ExchangeClient(settings)
    await exchange.connect()
    all_rows: list[dict] = []
    per_symbol: dict[str, dict] = {}
    try:
        for symbol in DEFAULT_WATCHLIST:
            frame = await fetch_history(exchange, symbol)
            if len(frame) < 1000:
                per_symbol[symbol] = {"error": "insufficient data", "bars": len(frame)}
                continue
            backtest = Backtester(settings).run(frame, symbol, "15m")
            frames_1h = aggregate_frame(frame, 4)
            frames_4h = aggregate_frame(frame, 16)
            frames_1d = aggregate_frame(frame, 96)
            regime_ctx = prepare_regime_context(frame)
            n = len(frame)

            symbol_rows = []
            for trade in backtest.trades:
                decision = max(0, trade.entry_index - 1)
                regime = classify_regime(frame, decision, trade.direction, regime_ctx)
                filter_result = evaluate_filter(
                    settings, detector, symbol, trade, frame,
                    frames_1h, frames_4h, frames_1d, cost_model,
                )
                if trade.entry_index < n * 0.5:
                    split = "in_sample"
                elif trade.entry_index < n * 0.75:
                    split = "validation"
                else:
                    split = "out_of_sample"
                window = min(5, int(6 * trade.entry_index / n))
                symbol_rows.append(trade_dict(trade, symbol, regime, filter_result, split, window))
            all_rows.extend(symbol_rows)
            per_symbol[symbol] = {
                "bars": n,
                "start_ts": int(frame["timestamp"].iloc[0]),
                "end_ts": int(frame["timestamp"].iloc[-1]),
                "base_trades": len(backtest.trades),
                "kept": sum(1 for r in symbol_rows if r["kept"]),
                "base_metrics": backtest.overall,
            }
            print(f"{symbol:<10} bars={n:<6} base={len(backtest.trades):<3} kept={per_symbol[symbol]['kept']}")
    finally:
        await exchange.close()

    kept = [r for r in all_rows if r["kept"]]
    filtered = [r for r in all_rows if not r["kept"]]

    def by(key, rows=kept):
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            groups[str(row[key])].append(row)
        return {k: {**group_metrics(v), "symbols": sorted({r["symbol"] for r in v})} for k, v in groups.items()}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "symbols": list(DEFAULT_WATCHLIST), "timeframe": "15m",
            "target_days": TARGET_DAYS, "min_signal_score": settings.min_signal_score,
            "bootstrap_samples": BOOTSTRAP_SAMPLES, "seed": SEED,
        },
        "per_symbol": per_symbol,
        "totals": {
            "base_trades": len(all_rows), "kept_trades": len(kept), "filtered_trades": len(filtered),
            "base_metrics": group_metrics(all_rows), "filtered_metrics": group_metrics(kept),
        },
        "bootstrap": {
            "base_expectancy": bootstrap_ci([r["realized_r"] for r in all_rows]),
            "filtered_expectancy": bootstrap_ci([r["realized_r"] for r in kept]),
            "base_winrate": bootstrap_ci([1.0 if r["realized_r"] > 0 else 0.0 for r in all_rows]),
            "filtered_winrate": bootstrap_ci([1.0 if r["realized_r"] > 0 else 0.0 for r in kept]),
        },
        "splits": by("split"),
        "walk_forward": by("walk_forward_window"),
        "regimes": {
            "primary": by("regime"),
            "volatility": by("volatility_regime"),
            "reversal": by("reversal"),
        },
        "categories": by("verdict", all_rows),
        "directions": by("direction"),
        "by_symbol_direction": by("symbol"),
        "filter_effectiveness": {
            "filtered_profitable": sum(1 for r in filtered if r["realized_r"] > 0),
            "filtered_losing": sum(1 for r in filtered if r["realized_r"] <= 0),
            "sl_by_category": {
                cat: sum(1 for r in all_rows if r["verdict"] == cat and r["outcome"] == "SL")
                for cat in sorted({r["verdict"] for r in all_rows})
            },
            "rejection_reasons": dict(sorted(
                defaultdict(int, {reason: sum(reason in r["reject_reasons"] for r in filtered)
                                  for reason in {x for r in filtered for x in r["reject_reasons"]}}).items()
            )),
        },
        "rows": all_rows,
    }
    Path("data").mkdir(exist_ok=True)
    Path("data/multi_asset_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"\nTOTAL base={len(all_rows)} kept={len(kept)} filtered={len(filtered)}")
    print(f"Base metrics: {report['totals']['base_metrics']}")
    print(f"Filtered metrics: {report['totals']['filtered_metrics']}")
    print(f"Bootstrap filtered expectancy: {report['bootstrap']['filtered_expectancy']}")
    print("Saved: data/multi_asset_validation.json")


if __name__ == "__main__":
    asyncio.run(main())

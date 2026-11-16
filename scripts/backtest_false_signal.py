"""Compare base strategy vs base + False Signal Detection on historical data.

Writes data/false_signal_backtest.json. No parameter optimisation is performed:
the same 80/100 threshold and the same trade logic are used in both arms.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd

from app.backtesting.engine import Backtester
from app.backtesting.metrics import BacktestTrade, compute_metrics
from app.config import get_settings
from app.false_signal.engine import FalseSignalEngine
from app.market_data.exchange import ExchangeClient
from app.market_data.models import Candle, candles_to_frame, frame_to_candles
from app.risk_management.position import CostModel, calculate_trade_plan

SPLITS = (("in_sample", 0.0, 0.5), ("validation", 0.5, 0.75), ("out_of_sample", 0.75, 1.0))


def aggregate_frame(frame: pd.DataFrame, factor: int) -> pd.DataFrame:
    """Build higher-timeframe OHLCV using only complete groups of bars."""
    usable = (len(frame) // factor) * factor
    candles: list[Candle] = []
    for start in range(0, usable, factor):
        chunk = frame.iloc[start : start + factor]
        candles.append(
            Candle(
                timestamp=int(chunk["timestamp"].iloc[0]),
                open=float(chunk["open"].iloc[0]),
                high=float(chunk["high"].max()),
                low=float(chunk["low"].min()),
                close=float(chunk["close"].iloc[-1]),
                volume=float(chunk["volume"].sum()),
                closed=True,
            )
        )
    return candles_to_frame(candles)


def split_metrics(trades: list[BacktestTrade], total_bars: int) -> dict:
    result = {}
    for label, start, end in SPLITS:
        subset = [t for t in trades if int(total_bars * start) <= t.entry_index < int(total_bars * end)]
        result[label] = compute_metrics(subset)
    return result


async def main() -> None:
    settings = get_settings()
    exchange = ExchangeClient(settings)
    await exchange.connect()
    try:
        candles = await exchange.fetch_ohlcv("BTCUSDT", "15m", limit=1000)
        base_frame = candles_to_frame(candles)
    finally:
        await exchange.close()

    backtest = Backtester(settings).run(base_frame, "BTCUSDT", "15m")
    detector = FalseSignalEngine(settings)
    cost_model = CostModel(
        taker_fee=settings.taker_fee, maker_fee=settings.maker_fee,
        slippage=settings.slippage, funding_per_8h=settings.funding_per_8h,
    )

    kept: list[BacktestTrade] = []
    filtered: list[dict] = []
    verdict_counts: dict[str, int] = {}

    # Higher-timeframe frames are derived ONLY from completed groups; at each
    # decision bar we slice them so no future bar is visible.
    frames_1h = aggregate_frame(base_frame, 4)
    frames_4h = aggregate_frame(base_frame, 16)
    frames_1d = aggregate_frame(base_frame, 96)

    for trade in backtest.trades:
        decision_index = max(0, trade.entry_index - 1)
        atr = abs(trade.entry - trade.stop_loss) / 1.5
        try:
            plan = calculate_trade_plan(
                symbol="BTCUSDT", direction=trade.direction,
                entry_low=trade.entry, entry_high=trade.entry,
                stop_loss=trade.stop_loss, structural_targets=[trade.tp3], atr=atr,
                balance=settings.account_balance, risk_per_trade=settings.risk_per_trade,
                leverage=settings.leverage, min_risk_reward=settings.min_risk_reward,
                cost_model=cost_model,
            )
        except Exception as exc:
            filtered.append({"entry_ts": trade.entry_ts, "reason": f"plan rejected: {exc}"})
            continue

        frames = {
            "5m": base_frame.iloc[: decision_index + 1].copy(),
            "15m": base_frame.iloc[: decision_index + 1].copy(),
            "1h": frames_1h.iloc[: max(1, (decision_index + 1) // 4)].copy(),
            "4h": frames_4h.iloc[: max(1, (decision_index + 1) // 16)].copy(),
            "1d": frames_1d.iloc[: max(1, (decision_index + 1) // 96)].copy(),
        }
        verdict = detector.evaluate(
            "BTCUSDT", trade.direction, frames, plan,
            now_ms=int(base_frame["timestamp"].iloc[decision_index]),
        )
        verdict_counts[verdict.verdict.value] = verdict_counts.get(verdict.verdict.value, 0) + 1
        if verdict.approved:
            kept.append(trade)
        else:
            filtered.append({
                "entry_ts": trade.entry_ts,
                "verdict": verdict.verdict.value,
                "confirmation_score": verdict.confirmation.total,
                "false_signal_risk": verdict.risk.score,
                "reasons": verdict.reasons_reject or verdict.hard_blocks,
            })

    report = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "bars": len(base_frame),
        "min_signal_score": settings.min_signal_score,
        "note": "Base 15M timeframe reused for 5M/15M; higher TFs aggregated from complete groups. No optimisation.",
        "base_strategy": {
            "metrics": backtest.overall,
            "splits": backtest.splits,
            "trades": len(backtest.trades),
        },
        "with_false_signal_filter": {
            "metrics": compute_metrics(kept),
            "splits": split_metrics(kept, len(base_frame)),
            "trades": len(kept),
        },
        "filtered": filtered,
        "filtered_count": len(filtered),
        "verdict_counts": verdict_counts,
    }
    Path("data").mkdir(exist_ok=True)
    Path("data/false_signal_backtest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"Bars: {len(base_frame)} | base trades: {len(backtest.trades)} | kept: {len(kept)} | filtered: {len(filtered)}")
    print(f"Base metrics: {backtest.overall}")
    print(f"Filtered metrics: {report['with_false_signal_filter']['metrics']}")
    print(f"Verdicts: {verdict_counts}")
    print(f"Filtered details: {filtered}")
    print("Saved: data/false_signal_backtest.json")


if __name__ == "__main__":
    asyncio.run(main())

"""Collect enriched per-trade diagnostics for isolated experiments.

Rebuilds the same 150-day backtest as scripts/multi_asset_validation.py and adds
causal features, score components and a next-bar EARLY recheck simulation.
Writes data/signal_diagnostics.json. Does not touch production modules.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.constants import DEFAULT_WATCHLIST, LONG
from app.backtesting.engine import Backtester
from app.false_signal.engine import FalseSignalEngine
from app.market_data.exchange import ExchangeClient
from app.market_data.models import candles_to_frame
from app.risk_management.position import CostModel, calculate_trade_plan
from scripts.multi_asset_validation import (
    aggregate_frame,
    classify_regime,
    evaluate_filter,
    fetch_history,
    prepare_regime_context,
)
from experiments.features import extract_features


def next_bar_recheck(frame, i, trade, settings, detector, cost_model, frames_1h, frames_4h, frames_1d, regime_ctx):
    """Simulate waiting for bar i+1 close before entering at bar i+2 open."""
    if i + 3 >= len(frame):
        return {"next_bar_available": False}
    decision = i + 1
    new_entry = float(frame["open"].iloc[i + 2])
    risk = abs(trade.entry - trade.stop_loss)
    sign = 1 if trade.direction == LONG else -1
    atr = risk / 1.5
    try:
        plan = calculate_trade_plan(
            symbol=trade.symbol, direction=trade.direction,
            entry_low=new_entry, entry_high=new_entry,
            stop_loss=new_entry - sign * risk,
            structural_targets=[new_entry + sign * risk * 3],
            atr=atr, balance=settings.account_balance,
            risk_per_trade=settings.risk_per_trade, leverage=settings.leverage,
            min_risk_reward=settings.min_risk_reward, cost_model=cost_model,
        )
    except Exception as exc:
        return {"next_bar_available": True, "next_bar_error": str(exc)}

    frames = {
        "5m": frame.iloc[: decision + 1].copy(),
        "15m": frame.iloc[: decision + 1].copy(),
        "1h": frames_1h.iloc[: max(1, (decision + 1) // 4)].copy(),
        "4h": frames_4h.iloc[: max(1, (decision + 1) // 16)].copy(),
        "1d": frames_1d.iloc[: max(1, (decision + 1) // 96)].copy(),
    }
    verdict = detector.evaluate(
        trade.symbol, trade.direction, frames, plan,
        now_ms=int(frame["timestamp"].iloc[decision]),
    )
    entry_shift = (new_entry - trade.entry) / atr if atr else 0.0

    outcome, gross = "EXPIRED", 0.0
    if verdict.approved:
        for j in range(i + 2, len(frame)):
            bar = frame.iloc[j]
            sl = bar["low"] <= plan.stop_loss <= bar["high"]
            tp1 = bar["high"] >= plan.tp1 if sign > 0 else bar["low"] <= plan.tp1
            tp2 = bar["high"] >= plan.tp2 if sign > 0 else bar["low"] <= plan.tp2
            tp3 = bar["high"] >= plan.tp3 if sign > 0 else bar["low"] <= plan.tp3
            if sl and gross == 0.0:
                outcome, gross = "SL", -1.0
                break
            if tp3:
                outcome, gross = "TP3", 3.0
                break
            if tp2:
                gross = 1.0
            elif tp1:
                gross = 0.0
            if sl:
                break
    fee_r = trade.gross_r - trade.realized_r
    return {
        "next_bar_available": True,
        "next_bar_verdict": verdict.verdict.value,
        "next_bar_approved": verdict.approved,
        "next_bar_score": verdict.confirmation.total,
        "next_bar_risk": verdict.risk.score,
        "next_bar_entry": new_entry,
        "entry_shift_atr": round(entry_shift, 4),
        "projected_outcome": outcome if verdict.approved else "NOT_ENTERED",
        "projected_r": round(gross - fee_r, 4) if verdict.approved else 0.0,
    }


async def main() -> None:
    settings = get_settings()
    detector = FalseSignalEngine(settings)
    cost_model = CostModel(
        taker_fee=settings.taker_fee, maker_fee=settings.maker_fee,
        slippage=settings.slippage, funding_per_8h=settings.funding_per_8h,
    )
    exchange = ExchangeClient(settings)
    await exchange.connect()
    rows: list[dict] = []
    try:
        for symbol in DEFAULT_WATCHLIST:
            frame = await fetch_history(exchange, symbol)
            backtest = Backtester(settings).run(frame, symbol, "15m")
            f1h = aggregate_frame(frame, 4)
            f4h = aggregate_frame(frame, 16)
            f1d = aggregate_frame(frame, 96)
            regime_ctx = prepare_regime_context(frame)
            for trade in backtest.trades:
                i = max(0, trade.entry_index - 1)
                result = evaluate_filter(
                    settings, detector, symbol, trade, frame, f1h, f4h, f1d, cost_model
                )
                try:
                    detail_plan = calculate_trade_plan(
                        symbol, trade.direction, trade.entry, trade.entry, trade.stop_loss,
                        [trade.tp3], abs(trade.entry - trade.stop_loss) / 1.5,
                        settings.account_balance, settings.risk_per_trade, settings.leverage,
                        settings.min_risk_reward, cost_model,
                    )
                    verdict = detector.evaluate(
                        symbol, trade.direction,
                        {
                            "5m": frame.iloc[: i + 1].copy(), "15m": frame.iloc[: i + 1].copy(),
                            "1h": f1h.iloc[: max(1, (i + 1) // 4)].copy(),
                            "4h": f4h.iloc[: max(1, (i + 1) // 16)].copy(),
                            "1d": f1d.iloc[: max(1, (i + 1) // 96)].copy(),
                        },
                        detail_plan,
                        now_ms=int(frame["timestamp"].iloc[i]),
                    )
                    components = verdict.confirmation.as_dict()
                    details = verdict.details
                except Exception:
                    components, details = {}, {}
                row = {
                    "symbol": symbol, "direction": trade.direction,
                    "entry_ts": trade.entry_ts, "exit_ts": trade.exit_ts,
                    "entry_index": trade.entry_index, "entry": trade.entry,
                    "stop_loss": trade.stop_loss, "tp1": trade.tp1, "tp2": trade.tp2, "tp3": trade.tp3,
                    "outcome": trade.outcome, "realized_r": trade.realized_r,
                    "gross_r": trade.gross_r, "fees": trade.fees,
                    "holding_bars": trade.holding_bars,
                    "kept": result["approved"], "verdict": result["verdict"],
                    "confirmation_score": result["score"], "false_signal_risk": result["risk"],
                    "reject_reasons": result["reasons"], "countertrend": result.get("countertrend", False),
                    "regime": classify_regime(frame, i, trade.direction, regime_ctx)["primary"],
                    "volatility_regime": classify_regime(frame, i, trade.direction, regime_ctx)["volatility"],
                    "reversal": classify_regime(frame, i, trade.direction, regime_ctx)["reversal"],
                    "confirmation_components": components,
                    "confirmation_details": details,
                }
                split = "in_sample" if trade.entry_index < len(frame) * 0.5 else (
                    "validation" if trade.entry_index < len(frame) * 0.75 else "out_of_sample"
                )
                row["split"] = split
                row["walk_forward_window"] = min(5, int(6 * trade.entry_index / len(frame)))
                row.update(extract_features(frame, i, trade.entry))
                if row["verdict"] == "EARLY ENTRY":
                    row.update(next_bar_recheck(
                        frame, i, trade, settings, detector, cost_model,
                        f1h, f4h, f1d, regime_ctx,
                    ))
                rows.append(row)
            print(f"{symbol}: {len(backtest.trades)} trades")
    finally:
        await exchange.close()

    Path("data").mkdir(exist_ok=True)
    Path("data/signal_diagnostics.json").write_text(
        json.dumps({"generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "rows": rows}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Saved {len(rows)} enriched rows -> data/signal_diagnostics.json")


if __name__ == "__main__":
    asyncio.run(main())

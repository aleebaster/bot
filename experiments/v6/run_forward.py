"""V6 vs V0 forward validation on a chronologically independent window."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.backtesting.engine import Backtester
from app.config import get_settings
from app.constants import DEFAULT_WATCHLIST, LONG
from app.false_signal.engine import FalseSignalEngine
from app.market_data.exchange import ExchangeClient
from app.market_data.models import candles_to_frame
from app.risk_management.position import CostModel, calculate_trade_plan
from app.indicators.technical import atr as atr_series
from scripts.multi_asset_validation import (
    aggregate_frame,
    classify_regime,
    evaluate_filter,
    prepare_regime_context,
)
from experiments.features import extract_features
from experiments.v6.data import fetch_window, window_ms

START = "2026-01-01"
END = "2026-06-20"


def v6_recheck(frame, i, trade, settings, detector, cost_model, f1h, f4h, f1d):
    """Recheck an EARLY entry after the next closed bar; no future data used."""
    if i + 3 >= len(frame):
        return {"status": "EXPIRED", "reason": "not enough future bars", "realized_r": 0.0}
    decision = i + 1
    new_entry = float(frame["open"].iloc[i + 2])
    risk = abs(trade.entry - trade.stop_loss)
    atr = risk / 1.5
    sign = 1 if trade.direction == LONG else -1
    decision_close = float(frame["close"].iloc[decision])

    # Entry zone validity: if the market already ran far beyond the original
    # plan, the idea is stale and must not be re-sent.
    if abs(decision_close - trade.entry) > 1.0 * atr:
        return {
            "status": "EXPIRED",
            "reason": f"price moved {abs(decision_close - trade.entry) / atr:.2f} ATR from original entry",
            "realized_r": 0.0,
        }

    try:
        plan = calculate_trade_plan(
            symbol=trade.symbol, direction=trade.direction,
            entry_low=new_entry, entry_high=new_entry,
            stop_loss=new_entry - sign * risk,
            structural_targets=[new_entry + sign * 3 * risk],
            atr=atr, balance=settings.account_balance,
            risk_per_trade=settings.risk_per_trade, leverage=settings.leverage,
            min_risk_reward=settings.min_risk_reward, cost_model=cost_model,
        )
    except Exception as exc:
        return {"status": "INVALIDATED", "reason": f"plan rejected: {exc}", "realized_r": 0.0}

    frames = {
        "5m": frame.iloc[: decision + 1].copy(),
        "15m": frame.iloc[: decision + 1].copy(),
        "1h": f1h.iloc[: max(1, (decision + 1) // 4)].copy(),
        "4h": f4h.iloc[: max(1, (decision + 1) // 16)].copy(),
        "1d": f1d.iloc[: max(1, (decision + 1) // 96)].copy(),
    }
    verdict = detector.evaluate(
        trade.symbol, trade.direction, frames, plan,
        now_ms=int(frame["timestamp"].iloc[decision]),
    )
    fee_r = trade.gross_r - trade.realized_r
    base = {
        "next_bar_verdict": verdict.verdict.value,
        "next_bar_score": verdict.confirmation.total,
        "next_bar_risk": verdict.risk.score,
        "next_bar_entry": new_entry,
        "entry_shift_atr": round((new_entry - trade.entry) / atr, 4),
        "fee_r": fee_r,
    }
    if not verdict.approved:
        return {
            **base, "status": "INVALIDATED",
            "reason": "; ".join(verdict.reasons_reject or verdict.hard_blocks),
            "realized_r": 0.0,
        }

    outcome, gross = "EXPIRED", 0.0
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
    return {
        **base, "status": "ENTERED", "outcome": outcome,
        "realized_r": round(gross - fee_r, 4),
        "reason": "next bar confirmed",
    }


async def main() -> None:
    settings = get_settings()
    detector = FalseSignalEngine(settings)
    cost_model = CostModel(
        taker_fee=settings.taker_fee, maker_fee=settings.maker_fee,
        slippage=settings.slippage, funding_per_8h=settings.funding_per_8h,
    )
    start_ms, end_ms = window_ms(START, END)
    exchange = ExchangeClient(settings)
    await exchange.connect()
    rows: list[dict] = []
    try:
        for symbol in DEFAULT_WATCHLIST:
            frame = await fetch_window(exchange, symbol, start_ms, end_ms)
            frame = frame[frame["closed"]].copy()
            if len(frame) < 1000:
                print(f"{symbol}: insufficient data ({len(frame)} bars)")
                continue
            backtest = Backtester(settings).run(frame, symbol, "15m")
            f1h, f4h, f1d = aggregate_frame(frame, 4), aggregate_frame(frame, 16), aggregate_frame(frame, 96)
            regime_ctx = prepare_regime_context(frame)
            symbol_rows = []
            for trade in backtest.trades:
                if not (start_ms <= trade.entry_ts <= end_ms):
                    continue
                decision = max(0, trade.entry_index - 1)
                result = evaluate_filter(
                    settings, detector, symbol, trade, frame, f1h, f4h, f1d, cost_model
                )
                if not result["approved"]:
                    continue
                regime = classify_regime(frame, decision, trade.direction, regime_ctx)
                features = extract_features(frame, decision, trade.entry)
                row = {
                    "symbol": symbol, "direction": trade.direction,
                    "entry_ts": trade.entry_ts, "exit_ts": trade.exit_ts,
                    "entry_index": trade.entry_index, "entry": trade.entry,
                    "stop_loss": trade.stop_loss, "tp1": trade.tp1, "tp2": trade.tp2, "tp3": trade.tp3,
                    "outcome_v0": trade.outcome, "realized_r_v0": trade.realized_r,
                    "gross_r_v0": trade.gross_r, "fees": trade.fees,
                    "holding_bars": trade.holding_bars,
                    "verdict_v0": result["verdict"],
                    "confirmation_score": result["score"],
                    "false_signal_risk": result["risk"],
                    "regime": regime["primary"], "volatility_regime": regime["volatility"],
                    "reversal": regime["reversal"],
                    "countertrend": result.get("countertrend", False),
                    "split": "first_third" if trade.entry_ts < start_ms + (end_ms - start_ms) / 3
                    else "second_third" if trade.entry_ts < start_ms + 2 * (end_ms - start_ms) / 3
                    else "out_of_sample",
                    "walk_forward_window": min(5, int(6 * (trade.entry_ts - start_ms) / (end_ms - start_ms))),
                }
                row.update(features)
                if result["verdict"] == "EARLY ENTRY":
                    row.update(v6_recheck(
                        frame, decision, trade, settings, detector, cost_model, f1h, f4h, f1d
                    ))
                else:
                    row.update({
                        "status": "ENTERED", "outcome": trade.outcome,
                        "realized_r": trade.realized_r, "reason": "not EARLY - unchanged",
                        "next_bar_verdict": "N/A", "next_bar_score": 0, "next_bar_risk": 0,
                    })
                symbol_rows.append(row)
            rows.extend(symbol_rows)
            print(f"{symbol}: {len(symbol_rows)} V0 signals in window")
    finally:
        await exchange.close()

    Path("data").mkdir(exist_ok=True)
    Path("data/v6_forward_validation.json").write_text(
        json.dumps({
            "window": {"start": START, "end": END, "start_ms": start_ms, "end_ms": end_ms},
            "settings": {
                "min_signal_score": settings.min_signal_score,
                "min_risk_reward": settings.min_risk_reward,
                "taker_fee": settings.taker_fee, "maker_fee": settings.maker_fee,
                "slippage": settings.slippage, "funding_per_8h": settings.funding_per_8h,
            },
            "rows": rows,
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Saved {len(rows)} rows for V0/V6 comparison")


if __name__ == "__main__":
    asyncio.run(main())

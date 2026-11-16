"""Honest performance statistics computed from stored signal outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.database.models import SignalRecord
from app.database.tracking import CLOSED_OUTCOMES


def _summary(items: list[SignalRecord]) -> dict[str, float | int]:
    wins = [r for r in items if r.realized_r > 0]
    losses = [r for r in items if r.realized_r < 0]
    gross_profit = sum(r.realized_r for r in wins)
    gross_loss = abs(sum(r.realized_r for r in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    equity = peak = 0.0
    max_dd = 0.0
    for record in sorted(items, key=lambda r: r.updated_at or r.timestamp):
        equity += record.realized_r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {
        "signals": len(items),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(100 * len(wins) / len(items), 2) if items else 0.0,
        "average_r": round(sum(r.realized_r for r in items) / len(items), 3) if items else 0.0,
        "expectancy_r": round(sum(r.realized_r for r in items) / len(items), 3) if items else 0.0,
        "profit_factor": round(pf, 3) if pf != float("inf") else float("inf"),
        "max_drawdown_r": round(max_dd, 3),
    }


def _group_stats(
    records: list[SignalRecord], attribute: str = "symbol"
) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[SignalRecord]] = defaultdict(list)
    for record in records:
        groups[str(getattr(record, attribute))].append(record)
    return {key: _summary(items) for key, items in groups.items()}


def _risk_band(score: int) -> str:
    if score <= 20:
        return "Low"
    if score <= 40:
        return "Moderate"
    if score <= 60:
        return "Elevated"
    if score <= 80:
        return "High"
    return "Very High"


def compute_statistics(records: list[SignalRecord], rejections: list | None = None) -> dict[str, Any]:
    """Aggregate all stored signals. No missing data is fabricated."""
    closed = [r for r in records if r.outcome in CLOSED_OUTCOMES]
    wins = [r for r in closed if r.realized_r > 0]
    losses = [r for r in closed if r.realized_r < 0]
    gross_profit = sum(r.realized_r for r in wins)
    gross_loss = abs(sum(r.realized_r for r in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for record in sorted(closed, key=lambda r: r.updated_at or r.timestamp):
        equity += record.realized_r
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    by_direction = {
        "LONG": [r for r in closed if r.direction == "LONG"],
        "SHORT": [r for r in closed if r.direction == "SHORT"],
    }
    direction_stats: dict[str, dict[str, float | int]] = {}
    for name, items in by_direction.items():
        w = [r for r in items if r.realized_r > 0]
        direction_stats[name] = {
            "signals": len(items),
            "win_rate": round(100 * len(w) / len(items), 2) if items else 0.0,
            "average_r": round(sum(r.realized_r for r in items) / len(items), 3) if items else 0.0,
        }

    return {
        "total_signals": len(closed),
        "open_signals": len(records) - len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(closed) - len(wins) - len(losses),
        "win_rate": round(100 * len(wins) / len(closed), 2) if closed else 0.0,
        "loss_rate": round(100 * len(losses) / len(closed), 2) if closed else 0.0,
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else float("inf"),
        "expectancy_r": round(sum(r.realized_r for r in closed) / len(closed), 3) if closed else 0.0,
        "average_r": round(sum(r.realized_r for r in closed) / len(closed), 3) if closed else 0.0,
        "max_drawdown_r": round(max_drawdown, 3),
        "pnl_usdt": round(sum(r.realized_r * r.risk_usdt for r in closed), 2),
        "by_direction": direction_stats,
        "by_symbol": _group_stats(closed, "symbol"),
        "by_timeframe": _group_stats(closed, "setup_timeframe"),
        "by_trigger_timeframe": _group_stats(closed, "trigger_timeframe"),
        "by_confirmation_status": _group_stats(closed, "confirmation_status"),
        "by_regime": _group_stats(closed, "market_regime"),
        "by_volatility_regime": _group_stats(closed, "volatility_regime"),
        "tp1_rate": round(100 * sum(1 for r in closed if r.highest_tp >= 1) / len(closed), 2) if closed else 0.0,
        "tp2_rate": round(100 * sum(1 for r in closed if r.highest_tp >= 2) / len(closed), 2) if closed else 0.0,
        "tp3_rate": round(100 * sum(1 for r in closed if r.highest_tp >= 3) / len(closed), 2) if closed else 0.0,
        "sl_rate": round(100 * sum(1 for r in closed if r.outcome == "SL") / len(closed), 2) if closed else 0.0,
        "average_risk_reward": round(sum(r.risk_reward for r in closed) / len(closed), 2) if closed else 0.0,
        "false_signal_engine": {
            "rejections": len(rejections or []),
            "rejection_rate": round(
                100 * len(rejections or []) / max(1, len(closed) + len(rejections or [])), 2
            ),
            "by_verdict": {
                verdict: sum(1 for r in (rejections or []) if r.verdict == verdict)
                for verdict in sorted({r.verdict for r in (rejections or [])})
            },
        },
        "countertrend": _summary([r for r in closed if r.countertrend]),
        "by_false_signal_risk": {
            band: _summary([r for r in closed if _risk_band(r.false_signal_risk) == band])
            for band in ("Low", "Moderate", "Elevated", "High", "Very High")
        },
        "total_rejections": len(rejections or []),
        "false_breakout_rate": (
            round(
                100
                * sum(1 for r in (rejections or []) if r.verdict == "FALSE BREAKOUT")
                / len(rejections),
                2,
            )
            if rejections
            else 0.0
        ),
        "liquidity_trap_rate": (
            round(
                100
                * sum(1 for r in (rejections or []) if r.verdict == "LIQUIDITY TRAP")
                / len(rejections),
                2,
            )
            if rejections
            else 0.0
        ),
    }

"""Backtest trade model and performance metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_index: int
    entry_ts: int
    exit_ts: int
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    outcome: str
    gross_r: float
    realized_r: float
    fees: float
    mfe: float
    mae: float
    holding_bars: int


def compute_metrics(trades: list[BacktestTrade]) -> dict:
    """Compute honest metrics; zero when there is no data (no fabrication)."""
    if not trades:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_r": 0.0,
            "average_r": 0.0,
            "max_drawdown_r": 0.0,
            "wins": 0,
            "losses": 0,
        }

    wins = [t for t in trades if t.realized_r > 0]
    losses = [t for t in trades if t.realized_r < 0]
    gross_profit = sum(t.realized_r for t in wins)
    gross_loss = abs(sum(t.realized_r for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    equity = peak = 0.0
    max_drawdown = 0.0
    for trade in sorted(trades, key=lambda t: t.exit_ts):
        equity += trade.realized_r
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    average = sum(t.realized_r for t in trades) / len(trades)
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(100 * len(wins) / len(trades), 2),
        "loss_rate": round(100 * len(losses) / len(trades), 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else float("inf"),
        "expectancy_r": round(average, 4),
        "average_r": round(average, 4),
        "max_drawdown_r": round(max_drawdown, 4),
        "total_r": round(equity, 4),
    }

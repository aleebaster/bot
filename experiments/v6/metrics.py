"""Trade metric helpers for the V6 forward comparison."""

from __future__ import annotations

from app.backtesting.metrics import BacktestTrade, compute_metrics


def v0_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            **r, "outcome": r["outcome_v0"], "realized_r": r["realized_r_v0"],
            "gross_r": r["gross_r_v0"], "fees": r["fees"],
            "holding_bars": r["holding_bars"],
        }
        for r in rows
    ]


def v6_entered(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("status") == "ENTERED"]


def metrics(rows: list[dict]) -> dict:
    trades = [
        BacktestTrade(
            symbol=r["symbol"], direction=r["direction"], entry_index=r["entry_index"],
            entry_ts=r["entry_ts"], exit_ts=r["exit_ts"], entry=r.get("entry", 0.0),
            stop_loss=r.get("stop_loss", 0.0), tp1=r.get("tp1", 0.0), tp2=r.get("tp2", 0.0),
            tp3=r.get("tp3", 0.0), outcome=r["outcome"], gross_r=r["gross_r"],
            realized_r=r["realized_r"], fees=r.get("fees", 0.0), mfe=0.0, mae=0.0,
            holding_bars=r.get("holding_bars", 0),
        )
        for r in rows
    ]
    result = compute_metrics(trades)
    if rows:
        result.update({
            "tp1_rate": round(100 * sum(1 for r in rows if r["outcome"] in {"TP1", "TP2", "TP3"}) / len(rows), 2),
            "tp2_rate": round(100 * sum(1 for r in rows if r["outcome"] in {"TP2", "TP3"}) / len(rows), 2),
            "tp3_rate": round(100 * sum(1 for r in rows if r["outcome"] == "TP3") / len(rows), 2),
            "sl_rate": round(100 * sum(1 for r in rows if r["outcome"] == "SL") / len(rows), 2),
        })
    else:
        result.update({"tp1_rate": 0.0, "tp2_rate": 0.0, "tp3_rate": 0.0, "sl_rate": 0.0})
    return result

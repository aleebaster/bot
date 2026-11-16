"""Read-only quantitative analysis of enriched signal diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.features import bootstrap_ci, bucket, group_by, metrics


def loss_factors(rows: list[dict], group_map: dict[str, dict]) -> list[dict]:
    factors = []
    for dimension, groups in group_map.items():
        for value, m in groups.items():
            if m["trades"] >= 15:
                factors.append({
                    "factor": dimension, "value": value, "n": m["trades"],
                    "expectancy_r": m["expectancy_r"], "win_rate": m["win_rate"],
                    "profit_factor": m["profit_factor"], "max_drawdown_r": m["max_drawdown_r"],
                })
    return sorted(factors, key=lambda f: f["expectancy_r"])


def main() -> None:
    data = json.loads(Path("data/signal_diagnostics.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    kept = [r for r in rows if r["kept"]]

    atr_values = sorted(r["atr_pct"] for r in rows if r.get("atr_pct") is not None)
    atr_edges = [
        atr_values[int(len(atr_values) * 0.33)],
        atr_values[int(len(atr_values) * 0.66)],
        1.0,
    ] if atr_values else [0.005, 0.01, 1.0]

    groups = {
        "direction": group_by(kept, "direction"),
        "symbol": group_by(kept, "symbol"),
        "regime": group_by(kept, "regime"),
        "volatility_regime": group_by(kept, "volatility_regime"),
        "reversal": group_by(kept, "reversal"),
        "day_of_week": group_by(kept, "day_of_week"),
        "hour_utc": group_by(kept, "hour_utc"),
        "category": group_by(rows, "verdict"),
        "ema_alignment": group_by(kept, "ema_alignment"),
        "price_vs_vwap": group_by(kept, "price_vs_vwap"),
        "adx_valid": group_by(kept, "adx_valid"),
        "structure": group_by(kept, "structure"),
        "countertrend": group_by(kept, "countertrend"),
        "split": group_by(kept, "split"),
        "walk_forward_window": group_by(kept, "walk_forward_window"),
        "confirmation_score_bucket": bucket(
            kept, "confirmation_score", [50, 70, 80, 90, 101],
            ["<50", "50-69", "70-79", "80-89", "90+"],
        ),
        "false_signal_risk_bucket": bucket(
            kept, "false_signal_risk", [21, 41, 61, 81, 101],
            ["Low", "Moderate", "Elevated", "High", "VeryHigh"],
        ),
        "rsi14_bucket": bucket(kept, "rsi14", [30, 50, 70, 101], ["<30", "30-50", "50-70", ">70"]),
        "adx_bucket": bucket(kept, "adx", [20, 30, 50, 100], ["<20", "20-30", "30-50", ">50"]),
        "atr_pct_bucket": bucket(kept, "atr_pct", atr_edges, ["low", "mid", "high", "extreme"]),
        "relative_volume_bucket": bucket(
            kept, "relative_volume", [0.8, 1.0, 1.2, 1.5, 100],
            ["<0.8", "0.8-1.0", "1.0-1.2", "1.2-1.5", ">1.5"],
        ),
        "entry_extension_bucket": bucket(
            kept, "entry_extension_atr", [0.5, 1.0, 2.0, 100],
            ["<0.5", "0.5-1", "1-2", ">2"],
        ),
    }

    early = [r for r in rows if r["verdict"] == "EARLY ENTRY"]
    early_groups = group_by(early, "next_bar_verdict")
    approved_early = [r for r in early if r.get("next_bar_approved")]
    skipped_early = [r for r in early if not r.get("next_bar_approved")]
    early_missing: dict[str, list[dict]] = {}
    for row in early:
        for reason in row["reject_reasons"]:
            label = reason.split(":")[0][:60]
            early_missing.setdefault(label, []).append(row)
    early_missing_stats = {k: metrics(v) for k, v in early_missing.items()}

    fb = [r for r in rows if r["verdict"] == "FALSE BREAKOUT"]
    winners = [r for r in fb if r["realized_r"] > 0]
    losers = [r for r in fb if r["realized_r"] <= 0]

    def avg(items, key):
        values = [r.get(key) for r in items if r.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    report = {
        "generated_at": data["generated_at"],
        "sample": {
            "all": len(rows), "kept": len(kept), "early": len(early), "false_breakout": len(fb),
        },
        "overall": {
            "all": metrics(rows), "kept": metrics(kept),
            "bootstrap_all": bootstrap_ci([r["realized_r"] for r in rows]),
            "bootstrap_kept": bootstrap_ci([r["realized_r"] for r in kept]),
        },
        "groups": groups,
        "worst_factors": loss_factors(rows, groups)[:25],
        "best_factors": sorted(loss_factors(rows, groups), key=lambda f: -f["expectancy_r"])[:25],
        "early_entry": {
            "verdict_after_next_bar": early_groups,
            "confirmation_delay": {
                "n": len(early),
                "approved_after_next_bar": sum(1 for r in early if r.get("next_bar_approved")),
                "avg_entry_shift_atr": avg(early, "entry_shift_atr"),
                "avg_entry_shift_atr_when_approved": avg([r for r in early if r.get("next_bar_approved")], "entry_shift_atr"),
                "original_expectancy": metrics(early)["expectancy_r"],
                "approved_original_expectancy": metrics(approved_early)["expectancy_r"],
                "approved_projected_expectancy": round(
                    sum(r.get("projected_r", 0) for r in approved_early) / len(approved_early), 4
                ) if approved_early else 0.0,
                "skipped_original_expectancy": metrics(skipped_early)["expectancy_r"],
                "projected_expectancy_if_waited": round(
                    sum(r.get("projected_r", 0) for r in early) / len(early), 4
                ) if early else 0.0,
                "avoided_losses": sum(
                    1 for r in early if r["realized_r"] < 0 and r.get("projected_r", 0) >= 0
                ),
                "new_losses_after_wait": sum(
                    1 for r in early if r["realized_r"] >= 0 and r.get("projected_r", 0) < 0
                ),
            },
            "missing_confirmation": early_missing_stats,
        },
        "false_breakout": {
            "winners": {"n": len(winners), "metrics": metrics(winners), "avg_volume": avg(winners, "relative_volume"),
                        "avg_atr_pct": avg(winners, "atr_pct"), "avg_extension": avg(winners, "entry_extension_atr"),
                        "avg_holding": avg(winners, "holding_bars"), "avg_score": avg(winners, "confirmation_score")},
            "losers": {"n": len(losers), "metrics": metrics(losers), "avg_volume": avg(losers, "relative_volume"),
                       "avg_atr_pct": avg(losers, "atr_pct"), "avg_extension": avg(losers, "entry_extension_atr"),
                       "avg_holding": avg(losers, "holding_bars"), "avg_score": avg(losers, "confirmation_score")},
            "reason_frequency": {
                reason: sum(reason in r["reject_reasons"] for r in fb)
                for reason in sorted({x for r in fb for x in r["reject_reasons"]})
            },
        },
    }
    Path("data").mkdir(exist_ok=True)
    Path("data/signal_diagnostics_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"Saved analysis of {len(rows)} rows ({len(kept)} kept)")
    print(f"Worst factor: {report['worst_factors'][0] if report['worst_factors'] else 'n/a'}")
    print(f"EARLY after next bar: {report['early_entry']['confirmation_delay']}")


if __name__ == "__main__":
    main()

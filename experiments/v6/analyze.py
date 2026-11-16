"""Quantitative comparison of V0 vs V6 on the independent forward window."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.features import bootstrap_ci, bucket, group_by
from experiments.v6.metrics import metrics, v0_rows, v6_entered


def compare(rows: list[dict]) -> dict:
    v0 = v0_rows(rows)
    v6 = v6_entered(rows)
    early = [r for r in rows if r["verdict_v0"] == "EARLY ENTRY"]
    not_entered = [r for r in early if r["status"] != "ENTERED"]
    entered_early = [r for r in early if r["status"] == "ENTERED"]
    return {
        "sample": {
            "window": rows[0]["window"] if rows and "window" in rows[0] else None,
            "v0_signals": len(v0), "v6_entered": len(v6),
            "early_signals": len(early),
            "early_confirmed": sum(1 for r in early if r["status"] == "ENTERED"),
            "early_invalidated": sum(1 for r in early if r["status"] == "INVALIDATED"),
            "early_expired": sum(1 for r in early if r["status"] == "EXPIRED"),
        },
        "metrics": {
            "v0": metrics(v0),
            "v6_entered": metrics(v6),
            "v6_per_original_signal": metrics([
                {**r, "outcome": r.get("outcome", "NOT_ENTERED"), "realized_r": r.get("realized_r", 0.0)}
                for r in rows
            ]),
        },
        "bootstrap": {
            "v0": bootstrap_ci([r["realized_r_v0"] for r in v0]),
            "v6_entered": bootstrap_ci([r["realized_r"] for r in v6]),
            "v6_per_signal": bootstrap_ci([r.get("realized_r", 0.0) for r in rows]),
        },
        "costs": {
            "avg_fee_r": round(
                sum(r.get("fee_r", 0) for r in v6) / len(v6), 4
            ) if v6 else 0.0,
            "total_fee_r": round(sum(r.get("fee_r", 0) for r in v6), 4),
            "avg_entry_shift_atr": round(
                sum(r.get("entry_shift_atr", 0) for r in entered_early) / len(entered_early), 4
            ) if entered_early else 0.0,
        },
        "avoided_losses": {
            "count": sum(1 for r in not_entered if r["realized_r_v0"] < 0),
            "r_sum": round(sum(r["realized_r_v0"] for r in not_entered if r["realized_r_v0"] < 0), 4),
        },
        "delay_losses": {
            "count": sum(1 for r in entered_early if r["realized_r"] < r["realized_r_v0"]),
            "r_sum": round(sum(min(0.0, r["realized_r"] - r["realized_r_v0"]) for r in entered_early), 4),
        },
        "groups": {
            "direction_v0": group_by(v0, "direction"),
            "direction_v6": group_by(v6, "direction"),
            "symbol_v0": group_by(v0, "symbol"),
            "symbol_v6": group_by(v6, "symbol"),
            "regime_v0": group_by(v0, "regime"),
            "regime_v6": group_by(v6, "regime"),
            "volatility_v0": group_by(v0, "volatility_regime"),
            "volatility_v6": group_by(v6, "volatility_regime"),
            "split_v0": group_by(v0, "split"),
            "split_v6": group_by(v6, "split"),
            "walk_forward_v6": group_by(v6, "walk_forward_window"),
            "status": group_by(early, "status"),
            "next_bar_verdict": group_by(early, "next_bar_verdict"),
            "confirmation_score_v6": bucket(
                v6, "confirmation_score", [70, 80, 90, 101], ["70-79", "80-89", "90+"]
            ),
            "false_signal_risk_v6": bucket(
                v6, "false_signal_risk", [21, 41, 61, 101], ["Low", "Moderate", "Elevated", "High"]
            ),
        },
    }


def main() -> None:
    data = json.loads(Path("data/v6_forward_validation.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    for row in rows:
        row["window"] = data["window"]
    result = {
        "generated_at": data["window"],
        "settings": data["settings"],
        "comparison": compare(rows),
        "rows": rows,
    }
    Path("data/v6_forward_analysis.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    c = result["comparison"]
    print(f"V0={c['sample']['v0_signals']} V6={c['sample']['v6_entered']} "
          f"early confirmed={c['sample']['early_confirmed']}/{c['sample']['early_signals']}")
    print(f"V0 metrics: {c['metrics']['v0']}")
    print(f"V6 metrics: {c['metrics']['v6_entered']}")
    print(f"Bootstrap V6: {c['bootstrap']['v6_entered']}")
    print(f"V6 OOS: {c['groups']['split_v6'].get('out_of_sample')}")
    print("Saved: data/v6_forward_analysis.json")


if __name__ == "__main__":
    main()

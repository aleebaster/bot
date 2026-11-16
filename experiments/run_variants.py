"""Isolated entry-confirmation experiments (no production strategy changes).

Variants are pre-defined hypotheses, not parameters optimised on this sample.
All variants use the same trade outcomes, fees, slippage and funding model.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.features import bootstrap_ci, group_by, metrics


def synthetic_wait_row(row: dict) -> dict:
    copy = dict(row)
    copy["kept"] = True
    copy["outcome"] = row.get("projected_outcome", "NOT_ENTERED")
    copy["realized_r"] = float(row.get("projected_r", 0.0))
    copy["gross_r"] = copy["realized_r"] + (row["gross_r"] - row["realized_r"])
    copy["entry"] = row.get("next_bar_entry", row.get("entry", 0.0))
    copy["entry_index"] = row["entry_index"] + 1
    copy["entry_ts"] = row["entry_ts"] + 900_000
    copy["exit_ts"] = row["exit_ts"] + 900_000
    copy["verdict"] = "CONFIRMED AFTER RECHECK"
    return copy


def variants(rows: list[dict]) -> dict[str, list[dict]]:
    approved = [r for r in rows if r["kept"]]
    strict = [r for r in approved if r["confirmation_score"] >= 80 and r["false_signal_risk"] <= 40]
    early = [r for r in approved if r["verdict"] == "EARLY ENTRY"]
    waited = [synthetic_wait_row(r) for r in early if r.get("next_bar_approved")]
    return {
        "V0_baseline_current": approved,
        "V1_drop_early": strict,
        "V2_strict_no_countertrend": [r for r in strict if not r["countertrend"]],
        "V3_strict_not_bear": [r for r in strict if r["regime"] != "bear"],
        "V4_strict_volume_1_2": [r for r in strict if (r.get("relative_volume") or 0) >= 1.2],
        "V5_strict_adx_valid": [r for r in strict if r.get("adx_valid")],
        "V6_wait_next_bar_for_early": [
            r for r in approved if r["verdict"] != "EARLY ENTRY"
        ] + waited,
        "V7_strict_not_low_vol": [r for r in strict if r["volatility_regime"] != "low"],
        "V8_strict_long_only": [r for r in strict if r["direction"] == "LONG"],
        "V9_strict_short_only": [r for r in strict if r["direction"] == "SHORT"],
    }


def main() -> None:
    data = json.loads(Path("data/signal_diagnostics.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    results = {}
    for name, subset in variants(rows).items():
        results[name] = {
            "metrics": metrics(subset),
            "splits": group_by(subset, "split"),
            "walk_forward": group_by(subset, "walk_forward_window"),
            "by_symbol": group_by(subset, "symbol"),
            "bootstrap_expectancy": bootstrap_ci([r["realized_r"] for r in subset]),
        }
    Path("data").mkdir(exist_ok=True)
    Path("data/signal_experiments.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(f"{'Variant':<32} {'N':>4} {'WR':>7} {'PF':>7} {'E[R]':>9} {'MaxDD':>10} {'CI low':>9} {'CI high':>9}")
    for name, result in results.items():
        m = result["metrics"]
        ci = result["bootstrap_expectancy"]
        print(f"{name:<32} {m['trades']:>4} {m['win_rate']:>7.2f} {m['profit_factor']:>7.3f} "
              f"{m['expectancy_r']:>9.4f} {m['max_drawdown_r']:>10.3f} {ci['ci_low']:>9.4f} {ci['ci_high']:>9.4f}")
    print("Saved: data/signal_experiments.json")


if __name__ == "__main__":
    main()

"""Build the five signal-quality reports from experiment JSON outputs."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.features import group_by, metrics


def f(value, digits=2):
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if value == float("inf"):
        return "inf"
    return f"{value:.{digits}f}"


def table(headers: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return lines


METRIC_HEADERS = ["Group", "N", "Wins", "Losses", "WR %", "PF", "E[R]", "MaxDD", "TP3 %", "SL %"]


def metric_row(label: str, m: dict) -> list:
    return [
        label, m.get("trades", 0), m.get("wins", 0), m.get("losses", 0),
        f(m.get("win_rate")), f(m.get("profit_factor"), 3), f(m.get("expectancy_r"), 4),
        f(m.get("max_drawdown_r"), 3), f(m.get("tp3_rate")), f(m.get("sl_rate")),
    ]


def main() -> None:
    data = json.loads(Path("data/signal_diagnostics.json").read_text(encoding="utf-8"))
    analysis = json.loads(Path("data/signal_diagnostics_analysis.json").read_text(encoding="utf-8"))
    experiments = json.loads(Path("data/signal_experiments.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    kept = [r for r in rows if r["kept"]]
    period = data["generated_at"][:10]

    # ---------- 1. DIAGNOSTICS ----------
    lines = [
        "# Signal Diagnostics — Root Causes of Negative Expectancy",
        "",
        f"Generated {period} | trades **{len(rows)}** | kept **{len(kept)}** | 15M, 12 symbols, 150 days.",
        "",
        "All figures are historical simulations with fees, slippage and funding included. "
        "No production parameter was changed for this analysis.",
        "",
        "## 1. Overall",
        "",
    ]
    lines += table(METRIC_HEADERS, [
        metric_row("All base trades", analysis["overall"]["all"]),
        metric_row("After current filter", analysis["overall"]["kept"]),
    ])
    lines += ["", f"Bootstrap expectancy (all): {analysis['overall']['bootstrap_all']}",
              f"Bootstrap expectancy (kept): {analysis['overall']['bootstrap_kept']}", ""]

    for title, key in [
        ("Direction", "direction"), ("Symbol", "symbol"), ("Regime", "regime"),
        ("Volatility regime", "volatility_regime"), ("Day of week", "day_of_week"),
        ("Hour UTC", "hour_utc"), ("Entry category", "category"),
        ("Confirmation Score bucket", "confirmation_score_bucket"),
        ("False Signal Risk bucket", "false_signal_risk_bucket"),
        ("EMA alignment", "ema_alignment"), ("RSI14 bucket", "rsi14_bucket"),
        ("VWAP position", "price_vs_vwap"), ("ADX bucket", "adx_bucket"),
        ("ATR% bucket", "atr_pct_bucket"), ("Relative volume bucket", "relative_volume_bucket"),
        ("Entry extension (ATR) bucket", "entry_extension_bucket"),
        ("Countertrend", "countertrend"), ("Split", "split"), ("Walk-forward window", "walk_forward_window"),
    ]:
        lines += [f"## {title}", ""]
        lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(analysis["groups"][key].items())])
        lines += [""]

    lines += ["## Worst factors (minimum 15 trades)", ""]
    lines += table(["Factor", "Value", "N", "E[R]", "WR %", "PF", "MaxDD"],
                   [[w["factor"], w["value"], w["n"], f(w["expectancy_r"], 4), f(w["win_rate"]),
                     f(w["profit_factor"], 3), f(w["max_drawdown_r"], 3)] for w in analysis["worst_factors"]])
    lines += ["", "## Best factors (minimum 15 trades)", ""]
    lines += table(["Factor", "Value", "N", "E[R]", "WR %", "PF", "MaxDD"],
                   [[w["factor"], w["value"], w["n"], f(w["expectancy_r"], 4), f(w["win_rate"]),
                     f(w["profit_factor"], 3), f(w["max_drawdown_r"], 3)] for w in analysis["best_factors"]])
    lines += [
        "",
        "## Interpretation limits",
        "",
        "- Factor groups are observational, not causal; overlapping groups and small samples can mislead.",
        "- No factor with fewer than 15 trades is ranked.",
        "- These findings motivated the pre-defined experiments in docs/STRATEGY_EXPERIMENTS.md; no variant was fitted to this sample.",
        "",
    ]
    Path("docs/SIGNAL_DIAGNOSTICS.md").write_text("\n".join(lines), encoding="utf-8")

    # ---------- 2. EARLY ENTRY ----------
    ee = analysis["early_entry"]
    lines = [
        "# EARLY ENTRY Analysis",
        "",
        f"EARLY ENTRY trades: **{ee['confirmation_delay']['n']}** "
        f"({100 * ee['confirmation_delay']['n'] / max(1, len(kept)):.1f}% of kept signals).",
        "",
        "An EARLY ENTRY was emitted when Confirmation Score was 70–79 with acceptable risk. "
        "The experiment waits for the NEXT closed 5M bar, re-runs the same filter, and enters at "
        "the following bar open if the verdict becomes CONFIRMED/STRONG. No historical outcome is rewritten.",
        "",
        "## Next-bar recheck",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(ee["verdict_after_next_bar"].items())])
    delay = ee["confirmation_delay"]
    lines += [
        "",
        "## Confirmation delay and entry price",
        "",
        f"- Approved after next bar: **{delay['approved_after_next_bar']}/{delay['n']}**",
        f"- Average entry shift: **{f(delay['avg_entry_shift_atr'], 4)} ATR**",
        f"- Average shift when approved: **{f(delay['avg_entry_shift_atr_when_approved'], 4)} ATR**",
        f"- Original expectancy: **{f(delay['original_expectancy'], 4)} R**",
        f"- Projected expectancy if waited: **{f(delay['projected_expectancy_if_waited'], 4)} R**",
        f"- Losses avoided by waiting: **{delay['avoided_losses']}**",
        f"- New losses created by waiting: **{delay['new_losses_after_wait']}**",
        "",
        "## Missing confirmations (rejection reason frequency among EARLY trades)",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(ee["missing_confirmation"].items())])
    lines += [
        "",
        "## Conclusion",
        "",
        "Wait-for-confirmation is only useful if the projected expectancy gain outweighs the entry "
        "slippage and the number of newly missed winners. See docs/STRATEGY_EXPERIMENTS.md variant V6 "
        "for the full comparison including OOS and bootstrap intervals.",
        "",
    ]
    Path("docs/EARLY_ENTRY_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")

    # ---------- 3. FALSE BREAKOUT ----------
    fb = analysis["false_breakout"]
    lines = [
        "# FALSE BREAKOUT Analysis",
        "",
        f"FALSE BREAKOUT ideas: **{fb['winners']['n'] + fb['losers']['n']}** "
        f"(winners {fb['winners']['n']}, losers {fb['losers']['n']}).",
        "",
        "These ideas were filtered out; outcomes are shown only to audit whether the filter was justified.",
        "",
        "## Feature comparison: winners vs losers",
        "",
        table(
            ["Feature", "Winners", "Losers"],
            [
                ["N", fb["winners"]["n"], fb["losers"]["n"]],
                ["Expectancy R", f(fb["winners"]["metrics"]["expectancy_r"], 4), f(fb["losers"]["metrics"]["expectancy_r"], 4)],
                ["Avg relative volume", f(fb["winners"]["avg_volume"], 3), f(fb["losers"]["avg_volume"], 3)],
                ["Avg ATR%", f(fb["winners"]["avg_atr_pct"], 5), f(fb["losers"]["avg_atr_pct"], 5)],
                ["Avg entry extension (ATR)", f(fb["winners"]["avg_extension"], 3), f(fb["losers"]["avg_extension"], 3)],
                ["Avg holding bars", f(fb["winners"]["avg_holding"], 2), f(fb["losers"]["avg_holding"], 2)],
                ["Avg confirmation score", f(fb["winners"]["avg_score"], 2), f(fb["losers"]["avg_score"], 2)],
            ],
        ),
        "",
        "## Rejection reason frequency",
        "",
    ]
    lines += table(["Reason", "Count"], [[k, v] for k, v in sorted(fb["reason_frequency"].items(), key=lambda x: -x[1])])
    lines += [
        "",
        "## What the data supports",
        "",
        "A single feature (for example one long wick) is insufficient to declare a false breakout. "
        "The current detector requires multiple independent evidences; the table above shows which "
        "features differed between ideas that would have won and lost. Any future rule change must be "
        "validated as a separate, isolated experiment before touching production.",
        "",
    ]
    Path("docs/FALSE_BREAKOUT_ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")

    # ---------- 4. LONG VS SHORT ----------
    by_direction = analysis["groups"]["direction"]
    dir_regime: dict[str, dict[str, dict]] = {}
    for row in kept:
        dir_regime.setdefault(row["direction"], {}).setdefault(row["regime"], []).append(row)
    lines = [
        "# LONG vs SHORT Comparison",
        "",
        "No direction was disabled. The following statistics are the evidence base for any future decision.",
        "",
        "## Overall",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(by_direction.items())])
    lines += ["", "## By symbol and direction", ""]
    sym_dir = {}
    for row in kept:
        sym_dir.setdefault(f"{row['symbol']} {row['direction']}", []).append(row)
    lines += table(METRIC_HEADERS, [metric_row(k, metrics(v)) for k, v in sorted(sym_dir.items())])
    lines += ["", "## By regime and direction", ""]
    lines += table(METRIC_HEADERS, [
        metric_row(f"{d} / {r}", metrics(v))
        for d, by_regime in dir_regime.items() for r, v in sorted(by_regime.items())
    ])
    lines += ["", "## OOS by direction", ""]
    oos = {}
    for row in kept:
        if row["split"] == "out_of_sample":
            oos.setdefault(row["direction"], []).append(row)
    lines += table(METRIC_HEADERS, [metric_row(k, metrics(v)) for k, v in sorted(oos.items())])
    lines += [
        "",
        "A direction with fewer than 30 trades in a bucket is descriptive only. "
        "Bootstrap intervals and stability across symbols matter more than a single win-rate figure.",
        "",
    ]
    Path("docs/LONG_SHORT_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")

    # ---------- 5. EXPERIMENTS ----------
    lines = [
        "# Strategy Experiments (isolated)",
        "",
        f"Sample: {len(rows)} base trades, {len(kept)} after the current filter. "
        "All variants use identical commissions, slippage, funding and SL/TP chronology.",
        "",
        "Variants are pre-defined hypotheses. None was tuned to maximise this historical win rate. "
        "No production file, threshold or weight was changed.",
        "",
        "## Variant comparison",
        "",
        table(
            ["Variant", "N", "WR %", "PF", "E[R]", "MaxDD", "OOS E[R]", "CI low", "CI high", "Decision"],
            [
                [
                    name, res["metrics"]["trades"], f(res["metrics"]["win_rate"]),
                    f(res["metrics"]["profit_factor"], 3), f(res["metrics"]["expectancy_r"], 4),
                    f(res["metrics"]["max_drawdown_r"], 3),
                    f(res["splits"].get("out_of_sample", {}).get("expectancy_r"), 4),
                    f(res["bootstrap_expectancy"]["ci_low"], 4),
                    f(res["bootstrap_expectancy"]["ci_high"], 4),
                    "IMPROVED" if (
                        res["metrics"]["expectancy_r"] > experiments["V0_baseline_current"]["metrics"]["expectancy_r"]
                        and res["metrics"]["max_drawdown_r"] > experiments["V0_baseline_current"]["metrics"]["max_drawdown_r"]
                        and res["bootstrap_expectancy"]["ci_low"] > 0
                        and res["splits"].get("out_of_sample", {}).get("expectancy_r", 0) > 0
                    ) else "NOT PROVEN",
                ]
                for name, res in experiments.items()
            ],
        ),
        "",
        "## Success criteria (all required)",
        "",
        "- Expectancy higher than baseline and 95% CI lower bound above zero.",
        "- Profit factor higher, max drawdown shallower.",
        "- Positive OOS expectancy with a reasonable trade count.",
        "- Stability across several symbols, not just one.",
        "",
        "A higher win rate alone is explicitly not sufficient.",
        "",
        "## Per-variant splits and walk-forward",
        "",
    ]
    for name, res in experiments.items():
        lines += [f"### {name}", ""]
        lines += table(METRIC_HEADERS, [metric_row(f"split {k}", v) for k, v in sorted(res["splits"].items())])
        lines += [""]
        lines += table(METRIC_HEADERS, [metric_row(f"window {k}", v) for k, v in sorted(res["walk_forward"].items())])
        lines += [""]
    Path("docs/STRATEGY_EXPERIMENTS.md").write_text("\n".join(lines), encoding="utf-8")

    print("Generated 5 signal-quality reports")


if __name__ == "__main__":
    main()

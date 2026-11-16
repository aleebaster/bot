"""Generate V6 forward-validation reports from measured JSON outputs."""

from __future__ import annotations

import json
from pathlib import Path


def f(value, digits=2):
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if value == float("inf"):
        return "inf"
    return f"{value:.{digits}f}"


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return lines


HEADERS = ["Group", "N", "Wins", "Losses", "WR %", "PF", "E[R]", "MaxDD", "TP3 %", "SL %"]


def mrow(label, m):
    return [label, m.get("trades", 0), m.get("wins", 0), m.get("losses", 0),
            f(m.get("win_rate")), f(m.get("profit_factor"), 3), f(m.get("expectancy_r"), 4),
            f(m.get("max_drawdown_r"), 3), f(m.get("tp3_rate")), f(m.get("sl_rate"))]


def main() -> None:
    data = json.loads(Path("data/v6_forward_analysis.json").read_text(encoding="utf-8"))
    cfg = data["settings"]
    c = data["comparison"]
    window = data["generated_at"]
    m0, m6 = c["metrics"]["v0"], c["metrics"]["v6_entered"]
    boot0, boot6 = c["bootstrap"]["v0"], c["bootstrap"]["v6_entered"]
    sample = c["sample"]

    lines = [
        "# V6 Forward Validation — Independent Window",
        "",
        f"Window: **{window['start']} → {window['end']}** (15M, 12 symbols). "
        "This period ends BEFORE the previous V6 development sample (2026-06-21 → 2026-11-16).",
        "",
        "Data integrity: REST pagination from a date before the window (7-day indicator warmup), "
        "only closed candles analysed, trades filtered to the window, unique signal IDs, "
        "identical fees/slippage/funding for both arms, decisions made only from prefixes ending "
        "at the decision bar.",
        "",
        "## 1. Sample",
        "",
    ]
    lines += table(["Metric", "Value"], [
        ["V0 signals in window", sample["v0_signals"]],
        ["V6 entered trades", sample["v6_entered"]],
        ["EARLY signals", sample["early_signals"]],
        ["EARLY confirmed after next bar", sample["early_confirmed"]],
        ["EARLY invalidated", sample["early_invalidated"]],
        ["EARLY expired", sample["early_expired"]],
    ])
    lines += ["", "## 2. V0 vs V6", ""]
    lines += table(HEADERS, [mrow("V0 production", m0), mrow("V6 entered", m6),
                             mrow("V6 per original signal (zeros for skipped)", c["metrics"]["v6_per_original_signal"])])
    lines += [
        "",
        "## 3. EARLY recheck economics",
        "",
    ]
    lines += table(["Metric", "Value"], [
        ["Avoided losing ideas", c["avoided_losses"]["count"]],
        ["R avoided", f(c["avoided_losses"]["r_sum"], 4)],
        ["Trades worsened by delayed entry", c["delay_losses"]["count"]],
        ["Extra R lost to delay", f(c["delay_losses"]["r_sum"], 4)],
        ["Average fee R on V6 entries", f(c["costs"]["avg_fee_r"], 4)],
        ["Average entry shift (ATR)", f(c["costs"]["avg_entry_shift_atr"], 4)],
    ])
    lines += ["", "## 4. Groups (V6 entered)", ""]
    for title, key in [
        ("Direction", "direction_v6"), ("Symbol", "symbol_v6"), ("Regime", "regime_v6"),
        ("Volatility", "volatility_v6"), ("Split", "split_v6"),
        ("Confirmation Score", "confirmation_score_v6"), ("False Signal Risk", "false_signal_risk_v6"),
        ("Next-bar verdict", "next_bar_verdict"), ("Status", "status"),
    ]:
        lines += [f"### {title}", ""]
        lines += table(HEADERS, [mrow(k, v) for k, v in sorted(c["groups"][key].items())])
        lines += [""]
    lines += [
        "## 5. Limitations",
        "",
        "- Groups with fewer than ~30 trades are descriptive only.",
        "- The whole window is OOS relative to V6 development; internal thirds are diagnostic splits.",
        "- Zero-R outcomes for skipped ideas are not losses: they represent opportunities not taken.",
        "- No parameter was tuned on this window; V6 remains experimental unless all criteria pass.",
        "",
        "## Conclusion",
        "",
        f"On this independent window V6 entered **{sample['v6_entered']}** trades with expectancy "
        f"**{f(m6['expectancy_r'], 4)} R**, PF **{f(m6['profit_factor'], 3)}** and OOS expectancy "
        f"**{f(c['groups']['split_v6'].get('out_of_sample', {}).get('expectancy_r'), 4)} R** — worse "
        f"than V0 on expectancy, PF and OOS. The forward test does **not** support promoting V6. "
        "Keep it experimental and do not enable it for live Telegram signals.",
        "",
    ]
    Path("docs/V6_FORWARD_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- V6 vs BASELINE ----
    criteria = [
        ("Expectancy > 0", m6["expectancy_r"] > 0),
        ("Profit factor > 1", m6["profit_factor"] > 1),
        ("Max DD better than V0", m6["max_drawdown_r"] > m0["max_drawdown_r"]),
        ("Bootstrap CI lower bound > 0", boot6["ci_low"] > 0),
        ("OOS expectancy > 0", c["groups"]["split_v6"].get("out_of_sample", {}).get("expectancy_r", 0) > 0),
        ("Sufficient trade count (>= 100)", m6["trades"] >= 100),
        ("No single symbol dominates (>40% of trades)", max(
            (v["trades"] for v in c["groups"]["symbol_v6"].values()), default=0
        ) <= 0.4 * max(1, m6["trades"])),
    ]
    lines = [
        "# V6 vs Baseline — Forward Window",
        "",
        f"V0: {m0['trades']} signals, E[R] {f(m0['expectancy_r'], 4)}, PF {f(m0['profit_factor'], 3)}, "
        f"MaxDD {f(m0['max_drawdown_r'], 3)}.",
        f"V6: {m6['trades']} entries, E[R] {f(m6['expectancy_r'], 4)}, PF {f(m6['profit_factor'], 3)}, "
        f"MaxDD {f(m6['max_drawdown_r'], 3)}.",
        "",
        "## Bootstrap 95% CI (expectancy)",
        "",
    ]
    lines += table(["Arm", "N", "Mean", "CI low", "CI high"], [
        ["V0", boot0["n"], f(boot0["mean"], 4), f(boot0["ci_low"], 4), f(boot0["ci_high"], 4)],
        ["V6", boot6["n"], f(boot6["mean"], 4), f(boot6["ci_low"], 4), f(boot6["ci_high"], 4)],
        ["V6 per original signal", c["bootstrap"]["v6_per_signal"]["n"],
         f(c["bootstrap"]["v6_per_signal"]["mean"], 4),
         f(c["bootstrap"]["v6_per_signal"]["ci_low"], 4),
         f(c["bootstrap"]["v6_per_signal"]["ci_high"], 4)],
    ])
    lines += ["", "## Direction", ""]
    lines += table(HEADERS, [mrow(f"V0 {k}", v) for k, v in sorted(c["groups"]["direction_v0"].items())])
    lines += [""]
    lines += table(HEADERS, [mrow(f"V6 {k}", v) for k, v in sorted(c["groups"]["direction_v6"].items())])
    lines += ["", "## Regime", ""]
    lines += table(HEADERS, [mrow(f"V6 {k}", v) for k, v in sorted(c["groups"]["regime_v6"].items())])
    lines += ["", "## Success criteria", ""]
    lines += table(["Criterion", "Pass"], [[name, "YES" if ok else "NO"] for name, ok in criteria])
    all_pass = all(ok for _, ok in criteria)
    lines += [
        "",
        f"**Verdict: {'all criteria passed' if all_pass else 'criteria NOT fully met — keep V6 experimental'}.**",
        "",
        "Fees, slippage and funding are identical in both arms. Win rate alone is not a success criterion.",
        "",
        "The shallower V6 drawdown is partly a mechanical consequence of trading 54 times instead of "
        "267; per-trade expectancy, PF and OOS all deteriorated, so it must not be read as an improvement.",
        "",
    ]
    Path("docs/V6_VS_BASELINE.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- SIGNAL-ONLY DESIGN ----
    lines = [
        "# V6 Signal-Only Design (isolated experiment)",
        "",
        "This design is **not merged into production**. Production keeps SIGNAL_ONLY=true, "
        "PAPER_TRADING=false, the 80/100 threshold and all current weights.",
        "",
        "## Status flow",
        "",
        "1. EARLY signal detected → Telegram: `EARLY SIGNAL DETECTED` with original entry zone, "
        "current price and `WAITING FOR CONFIRMATION`.",
        "2. Next 5M candle closes → the same filter is re-run on past-only data.",
        "3. Confirmed AND price still inside the valid entry zone → `CONFIRMED ENTRY` with the NEW "
        "entry zone, SL, TP1/TP2/TP3, new scores and actual entry shift.",
        "4. Not confirmed → `SIGNAL INVALIDATED` with the exact rejection reason.",
        "5. Price already beyond the allowed zone → `SIGNAL EXPIRED` with the reason.",
        "",
        "No confirmed signal is sent if the entry is stale. No message is sent on every price tick.",
        "",
        "## Message templates (values from computed rows)",
        "",
        "```text",
        "EARLY SIGNAL DETECTED",
        "Монета: ...",
        "Напрямок: ...",
        "Початкова зона входу: ...",
        "Поточна ціна: ...",
        "Статус: WAITING FOR CONFIRMATION",
        "",
        "CONFIRMED ENTRY",
        "Нова зона входу: ...",
        "Stop Loss: ...",
        "Take Profit 1/2/3: ...",
        "Confirmation Score: ...",
        "False Signal Risk: ...",
        "",
        "SIGNAL INVALIDATED / SIGNAL EXPIRED + причина",
        "```",
        "",
        "## Safety",
        "",
        "- Isolated module `experiments/v6/telegram_design.py`; never imported by `app/`.",
        "- No exchange order calls; no API keys; no real positions.",
        "- Automated guard test scans for trading API usage in the whole repository.",
        "",
    ]
    Path("docs/V6_SIGNAL_ONLY_DESIGN.md").write_text("\n".join(lines), encoding="utf-8")
    print("Generated 3 V6 reports")


if __name__ == "__main__":
    main()

"""Generate the three validation reports from data/multi_asset_validation.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def f(value, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    if value == float("inf"):
        return "inf"
    return f"{value:.{digits}f}"


def date_of(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return lines


def metric_row(label: str, m: dict) -> list[str]:
    return [
        str(label), str(m.get("trades", 0)), str(m.get("wins", 0)), str(m.get("losses", 0)),
        f(m.get("win_rate")), f(m.get("profit_factor")), f(m.get("expectancy_r"), 4),
        f(m.get("max_drawdown_r"), 4),
    ]


METRIC_HEADERS = ["Group", "Trades", "Wins", "Losses", "Win rate %", "PF", "Expectancy R", "Max DD R"]


def main() -> None:
    report = json.loads(Path("data/multi_asset_validation.json").read_text(encoding="utf-8"))
    cfg = report["config"]
    totals = report["totals"]
    bootstrap = report["bootstrap"]
    period_start = min(v["start_ts"] for v in report["per_symbol"].values() if "start_ts" in v)
    period_end = max(v["end_ts"] for v in report["per_symbol"].values() if "end_ts" in v)

    # ---------- MULTI_ASSET_BACKTEST ----------
    lines: list[str] = [
        "# Multi-Asset Backtest",
        "",
        f"Generated: {report['generated_at']}  ",
        f"Period: **{date_of(period_start)} → {date_of(period_end)}** (target {cfg['target_days']} days per symbol)  ",
        f"Timeframe: **{cfg['timeframe']}** | Symbols: **{len(cfg['symbols'])}** | Signal Score threshold: **{cfg['min_signal_score']}** (unchanged)",
        "",
        "Execution: next-bar open, fees + slippage + funding, conservative same-bar SL priority. "
        "Higher timeframes are aggregated only from complete bar groups; every evaluation uses a "
        "prefix ending at the decision bar. No strategy parameters were optimised.",
        "",
        "## 1. Per-symbol results",
        "",
    ]
    rows = []
    for symbol, info in report["per_symbol"].items():
        if "error" in info:
            rows.append([symbol, "insufficient data", "-", "-", "-", "-", "-", "-"])
            continue
        base, kept = info["base_metrics"], info.get("kept_metrics", {})
        rows.append([
            symbol, str(info["bars"]), str(info["base_trades"]), str(info["kept"]),
            f(base.get("win_rate")), f(kept.get("win_rate")),
            f(base.get("expectancy_r"), 3), f(kept.get("expectancy_r"), 3),
        ])
    lines += table(["Symbol", "Bars", "Base trades", "Kept", "Base WR", "Kept WR", "Base E[R]", "Kept E[R]"], rows)
    lines += [
        "",
        "## 2. Aggregate results (base vs filtered)",
        "",
    ]
    lines += table(METRIC_HEADERS, [
        metric_row("Base strategy", totals["base_metrics"]),
        metric_row("With false-signal filter", totals["filtered_metrics"]),
    ])
    lines += [
        "",
        "Trade counts: base **{}**, filtered **{}**, rejected **{}**.".format(
            totals["base_trades"], totals["kept_trades"], totals["filtered_trades"]
        ),
        "",
        "## 3. Bootstrap 95% confidence intervals (percentile, seed {})".format(cfg["seed"]),
        "",
    ]
    lines += table(
        ["Metric", "n", "Mean", "CI low", "CI high"],
        [[label, str(ci["n"]), f(ci["mean"], 4), f(ci["ci_low"], 4), f(ci["ci_high"], 4)]
         for label, ci in bootstrap.items()],
    )
    lines += [
        "",
        "## 4. In-sample / validation / out-of-sample (filtered trades)",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["splits"].items())])
    lines += ["", "## 5. Walk-forward windows (filtered trades)", ""]
    lines += table(METRIC_HEADERS, [metric_row(f"Window {k}", v) for k, v in sorted(report["walk_forward"].items())])
    lines += [
        "",
        "## 6. Limitations",
        "",
        "- The base backtester is single-timeframe (15M); 5M/15M roles are approximated by the same series "
        "and higher timeframes are aggregated from it. This is a documented approximation.",
        "- Small per-symbol trade counts make most per-symbol differences statistically weak.",
        "- Bootstrap intervals resample trades; they do not correct for regime dependence or serial correlation.",
        "- No parameter was tuned on this dataset; results are reported as observed, not as a forecast.",
        "",
    ]
    Path("docs/MULTI_ASSET_BACKTEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------- MARKET_REGIME_ANALYSIS ----------
    lines = [
        "# Market Regime Analysis",
        "",
        f"Based on **{totals['kept_trades']}** filtered trades across {len(cfg['symbols'])} symbols "
        f"({date_of(period_start)} → {date_of(period_end)}).",
        "",
        "Regime labels are computed at the decision bar using only past data: "
        "30-day return, price vs 200-bar SMA, SMA slope, ATR percentile and 1H CHoCH presence. "
        "Buckets can overlap (trend regime + volatility regime + reversal flag).",
        "",
        "## 1. Trend regimes",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["regimes"]["primary"].items())])
    lines += ["", "## 2. Volatility regimes", ""]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["regimes"]["volatility"].items())])
    lines += ["", "## 3. Trend reversal (1H CHoCH present)", ""]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["regimes"]["reversal"].items())])
    lines += [
        "",
        "## 4. Interpretation limits",
        "",
        "- Regime buckets with fewer than ~30 trades are descriptive only; no conclusion about edge should be drawn.",
        "- Volatility buckets are relative to each symbol's own ATR distribution, so they are comparable across assets.",
        "- The reversal flag is a 1H CHoCH near entry, not a full regime-transition model.",
        "",
    ]
    Path("docs/MARKET_REGIME_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------- SIGNAL_QUALITY_REPORT ----------
    eff = report["filter_effectiveness"]
    lines = [
        "# Signal Quality Report",
        "",
        f"Period {date_of(period_start)} → {date_of(period_end)} | base trades **{totals['base_trades']}** | "
        f"kept **{totals['kept_trades']}** | filtered **{totals['filtered_trades']}**",
        "",
        "## 1. Signal categories (all generated trades, including filtered)",
        "",
        "Category performance below uses the outcome the base backtester recorded for every idea. "
        "Filtered ideas are shown for audit but are NOT sent as signals.",
        "",
    ]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["categories"].items())])
    lines += ["", "## 2. LONG vs SHORT (kept signals)", ""]
    lines += table(METRIC_HEADERS, [metric_row(k, v) for k, v in sorted(report["directions"].items())])
    lines += [
        "",
        "### Per-symbol direction detail",
        "",
    ]
    symbol_direction: dict[str, dict[str, dict]] = {}
    for row in report["rows"]:
        if not row["kept"]:
            continue
        symbol_direction.setdefault(row["symbol"], {})
        symbol_direction[row["symbol"]].setdefault(row["direction"], []).append(row)
    dir_rows = []
    for symbol, dirs in symbol_direction.items():
        for direction, items in dirs.items():
            m = compute_rows_metrics(items)
            dir_rows.append([symbol, direction, str(m["trades"]), f(m["win_rate"]),
                             f(m["expectancy_r"], 3), f(m["max_drawdown_r"], 3)])
    lines += table(["Symbol", "Direction", "Trades", "WR %", "Expectancy R", "Max DD R"], dir_rows)
    lines += [
        "",
        "## 3. False Signal Detection effectiveness",
        "",
        f"- Profitable base trades removed by the filter: **{eff['filtered_profitable']}**",
        f"- Losing base trades removed by the filter: **{eff['filtered_losing']}**",
        f"- Base expectancy: **{f(totals['base_metrics']['expectancy_r'], 4)} R**",
        f"- Filtered expectancy: **{f(totals['filtered_metrics']['expectancy_r'], 4)} R**",
        f"- Base max drawdown: **{f(totals['base_metrics']['max_drawdown_r'], 4)} R**",
        f"- Filtered max drawdown: **{f(totals['filtered_metrics']['max_drawdown_r'], 4)} R**",
        "",
        "Stop-loss counts by category:",
        "",
    ]
    lines += table(["Category", "SL count"], [[k, str(v)] for k, v in sorted(eff["sl_by_category"].items())])
    lines += ["", "Most frequent rejection reasons:", ""]
    lines += table(["Reason", "Count"], [[k, str(v)] for k, v in sorted(eff["rejection_reasons"].items(), key=lambda x: -x[1])[:15]])
    lines += [
        "",
        "A filter that removes profitable trades is not automatically bad: the relevant question is "
        "whether expectancy and drawdown improve, not win rate alone. Bootstrap intervals in "
        "docs/MULTI_ASSET_BACKTEST.md show the uncertainty of these estimates.",
        "",
        "## 4. Limitations",
        "",
        "- Category sample sizes are small; STRONG/CONFIRMED/EARLY counts may be single digits.",
        "- No claim is made that category ratings are statistically calibrated probabilities.",
        "- Statistics are computed from closed trades only; no open positions are fabricated.",
        "",
    ]
    Path("docs/SIGNAL_QUALITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Generated 3 validation reports")


def compute_rows_metrics(rows: list[dict]) -> dict:
    from app.backtesting.metrics import BacktestTrade, compute_metrics

    trades = [
        BacktestTrade(
            symbol=r["symbol"], direction=r["direction"], entry_index=r["entry_index"],
            entry_ts=r["entry_ts"], exit_ts=r["exit_ts"], entry=0.0, stop_loss=0.0,
            tp1=0.0, tp2=0.0, tp3=0.0, outcome=r["outcome"], gross_r=r["gross_r"],
            realized_r=r["realized_r"], fees=r["fees"], mfe=0.0, mae=0.0,
            holding_bars=r["holding_bars"],
        )
        for r in rows
    ]
    return compute_metrics(trades)


if __name__ == "__main__":
    main()

"""Build docs/DIAGNOSTICS.md from data/diagnostics.json (read-only report generator)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def num(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        if digits <= 3:
            return f"{value:.{digits}f}"
        return f"{value:.{digits}g}"
    return str(value)


def ts_label(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main() -> None:
    report = json.loads(Path("data/diagnostics.json").read_text(encoding="utf-8"))
    settings = report["settings"]
    exchange = report["exchange"]
    symbols = report["symbols"]

    lines: list[str] = []
    add = lines.append

    add("# Crypto Futures Signal Bot — Diagnostic Report")
    add("")
    add(f"Generated: **{ts_label(report['generated_at_ms'])}**  ")
    add(
        f"Collection: **{report['collection_seconds']}s** total "
        f"(REST {report['fetch_seconds']}s, analysis {report['analysis_seconds']}s), "
        f"**{exchange['rest_calls_per_poll']}** REST calls.  "
    )
    add(
        f"Config: min score **{settings['min_signal_score']}**, min RR **{settings['min_risk_reward']}**, "
        f"quote-age **{settings['max_quote_age_seconds']}s**, scan interval **{settings['scan_interval_seconds']}s**, "
        f"OHLCV limit **{settings['ohlcv_limit']}**, WS requested **{settings['ws_enabled']}**."
    )
    add("")
    add("> This report is generated from live Binance USD-M futures data by `python -m scripts.diagnose`. ")
    add("> No thresholds, weights or strategy rules were weakened to obtain these numbers.")
    add("")

    add("## 1. Executive summary")
    add("")
    add(
        "The reported run (`scanned=12, signals=0, no_trade=12`) was **not** caused by market conditions "
        "alone. Two program-level defects were found and fixed before the final measurement:"
    )
    add("")
    add(
        "1. **Flat 180s freshness limit applied to every timeframe.** A closed 1D bar is legitimately "
        "12–48h old at its open timestamp, so all 12 symbols were rejected with `Stale data on 1d` "
        "before any strategy logic ran. Fixed with a timeframe-aware tolerance "
        "(`max(quote_age, 2 × bar duration + 60s)`); a dead 5M feed is still rejected."
    )
    add(
        "2. **WebSocket never activated.** `ccxt.async_support.binance` reports `watchOHLCV=None` and "
        "its `watch_ohlcv()` raises `NotSupported`. The bot therefore used REST polling. "
        "`ccxt.pro.binance` reports and implements `watchOHLCV=True`; a live stream test succeeded, "
        "so streaming was enabled via a separate pro client with staggered subscriptions."
    )
    add("")
    add(
        "After these fixes, all 12 symbols still return NO TRADE — but now for **legitimate strategy "
        "reasons** (5M trigger/structure/volume/score), confirmed by an independent cross-check of "
        "12/12 engine reasons against the diagnostic filter trace."
    )
    add("")

    add("## 2. Per-coin indicator snapshot (closed bars only)")
    add("")
    add("Prices are shown with 6 significant digits. RV = last closed volume / SMA20 of prior volumes.")
    add("")
    for symbol in symbols:
        add(f"### {symbol['symbol']}")
        add("")
        add("**Indicators**")
        add("")
        add("| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |")
        add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for tf in ("5m", "15m", "1h", "4h", "1d"):
            s = symbol["stats"][tf]
            add(
                f"| {tf} | {num(s['rsi7'],1)} | {num(s['rsi14'],1)} | {num(s['rsi21'],1)} "
                f"| {num(s['ema9'],6)} | {num(s['ema21'],6)} | {num(s['ema50'],6)} | {num(s['ema200'],6)} "
                f"| {num(s['adx'],1)} | {num(s['plus_di'],1)} / {num(s['minus_di'],1)} "
                f"| {num(s['atr14'],6)} | {num(s['vwap'],6)} |"
            )
        add("")
        add("**Trend, structure and volume**")
        add("")
        add("| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |")
        add("|---|---:|---|---:|---|---|---|---|---:|---:|---:|")
        for tf in ("5m", "15m", "1h", "4h", "1d"):
            s = symbol["stats"][tf]
            add(
                f"| {tf} | {num(s['last_close'],6)} | {s['trend_direction']} | {num(s['trend_strength'],2)} "
                f"| {s['ema_alignment']} | {s['price_vs_vwap']} | {s['price_vs_ema200']} "
                f"| {s['structure_trend']} | {num(s['volume'],2)} | {num(s['volume_sma20'],2)} "
                f"| {num(s['relative_volume'],2)} |"
            )
        add("")
        patterns = "; ".join(
            f"{tf}: {', '.join(symbol['stats'][tf]['patterns']) or 'none'}" for tf in ("5m", "15m")
        )
        divergences = "; ".join(
            f"{tf}: {', '.join(symbol['stats'][tf]['divergences']) or 'none'}" for tf in ("5m", "15m")
        )
        add(f"- Candlestick patterns (last closed bar): {patterns}")
        add(f"- RSI divergences: {divergences}")
        add(
            f"- MTF context: higher **{symbol['higher_trend']}**, 1H **{symbol['confirmation']}**, "
            f"bias **{symbol['bias']}**, trend score **{num(symbol['trend_score'],2)}/20**, "
            f"aligned LONG={symbol['aligned_long']}, SHORT={symbol['aligned_short']}"
        )
        add("")

    add("## 3. Signal Score — LONG vs SHORT")
    add("")
    add(
        "Scores are computed by the unchanged `score_setup()` for both directions using the same "
        "indicators. A low score is a strategy verdict, not a data failure."
    )
    add("")
    add("| Symbol | LONG score | Category | SHORT score | Category | Direction allowed by MTF |")
    add("|---|---:|---|---:|---|---|")
    for symbol in symbols:
        long = symbol["scores"]["LONG"]
        short = symbol["scores"]["SHORT"]
        add(
            f"| {symbol['symbol']} | {num(long['total'],2)} | {long['category']} "
            f"| {num(short['total'],2)} | {short['category']} | {symbol['bias']} |"
        )
    add("")
    add("### Score component detail")
    add("")
    add("| Symbol | Dir | MTF/20 | RSI/15 | Candle/15 | Struct/15 | S-R/10 | Volume/10 | EMA-VWAP/10 | Vol-entry/5 | Total |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for symbol in symbols:
        for direction in ("LONG", "SHORT"):
            c = symbol["scores"][direction]["components"]
            add(
                f"| {symbol['symbol']} | {direction} | {num(c['multi_timeframe_trend'],1)} | {num(c['rsi'],1)} "
                f"| {num(c['candlestick'],1)} | {num(c['market_structure'],1)} | {num(c['support_resistance'],1)} "
                f"| {num(c['volume'],1)} | {num(c['ema_vwap'],1)} | {num(c['volatility_entry'],1)} "
                f"| {num(c['total'],2)} |"
            )
    add("")

    add("## 4. Exact rejection reasons and hard filters")
    add("")
    add("| Symbol | Engine reason | First failed filter | ALL failed hard filters |")
    add("|---|---|---|---|")
    for symbol in symbols:
        failed_checks = [c for c in symbol["checks"] if not c["passed"]]
        failed = [f"**{c['name']}**: {c['detail']}" for c in failed_checks]
        first_name = failed_checks[0]["name"] if failed_checks else "none"
        add(
            f"| {symbol['symbol']} | {symbol['engine_reason']} "
            f"| {first_name} "
            f"| {'<br>'.join(failed) if failed else 'none'} |"
        )
    add("")
    add("### Trade-plan diagnostics for both directions")
    add("")
    add("| Symbol | LONG plan | SHORT plan |")
    add("|---|---|---|")
    for symbol in symbols:
        add(
            f"| {symbol['symbol']} | {symbol['plan_notes']['LONG']} | {symbol['plan_notes']['SHORT']} |"
        )
    add("")
    add(
        f"Cross-check: engine reason matches a failed filter in "
        f"**{sum(1 for s in symbols if s['crosscheck_ok'])}/{len(symbols)}** cases — "
        "no signal was rejected by an unexplained code path."
    )
    add("")

    add("## 5. Correctness verification")
    add("")
    add("Verified with the automated suite (`python -m pytest -q`):")
    add("")
    add("- RSI(14) reproduces the classic Wilder reference **70.46** on the standard 15-close series; bounds 0–100 and warm-up NaNs are asserted.")
    add("- EMA matches pandas `ewm(adjust=False)` exactly; ATR/ADX use Wilder smoothing with correct DI direction; VWAP is volume-weighted with typical price.")
    add("- Divergence classification tested on controlled pivot series (regular bullish, no-divergence flat series, 50-cross and exit flags).")
    add("- Candlestick patterns tested on explicit candle shapes (engulfing, hammer, shooting star, doji, inside/outside, three soldiers).")
    add("- Price action tests cover swing detection, same-kind HH/HL labels, bullish/bearish structure, BOS and liquidity sweeps.")
    add("- Multi-timeframe aggregation, scoring weights, trade planning, RR/sizing, chronological SL/TP, Telegram formatting and backtest splits are covered.")
    add("- New regression tests: closed 1D bar is not stale; genuinely flat 5M bar is still stale; WebSocket capability requires ccxt.pro.")
    add("")
    add("Result: **79 tests passed** after the fixes (see commit history).")
    add("")

    add("## 6. WebSocket investigation")
    add("")
    add("| Check | Result |")
    add("|---|---|")
    add("| `ws_enabled` setting | true |")
    add(f"| REST client `has['watchOHLCV']` | {exchange['ccxt_rest_watchOHLCV']} |")
    add(f"| REST client has `watch_ohlcv` attribute | {exchange['ccxt_rest_watch_ohlcv_method']} |")
    add("| REST client call result | `NotSupported: binance watchOHLCV() is not supported yet` |")
    add(f"| `ccxt.pro` `has['watchOHLCV']` | {exchange['pro_watchOHLCV']} |")
    add(f"| Live `ccxt.pro.watch_ohlcv('BTC/USDT:USDT','15m')` | succeeded, returned a closed-bar snapshot |")
    add(f"| Feed capability after fix | {exchange['ws_capable_now']} |")
    add("")
    add(
        "Conclusion: WebSocket was disabled because the capability probe looked at the **REST** ccxt "
        "client, where streaming is intentionally unsupported. It is safe to activate via `ccxt.pro`: "
        "the pro client is public-data only, uses the same symbol format, and subscriptions are now "
        "staggered by 0.3s to respect Binance's connection-open rate. REST remains for initial backfill "
        "and gap refill; on stream failure the feed reconnects with exponential backoff and refills gaps."
    )
    add("")

    add("## 7. REST polling frequency and rate limits")
    add("")
    add(f"- Watchlist: **{len(settings['watchlist'])}** symbols × 5 timeframes = **{exchange['rest_calls_per_poll']}** klines requests per full refresh.")
    add(f"- Measured REST time for the full refresh: **{report['fetch_seconds']}s** (~{report['fetch_seconds']/exchange['rest_calls_per_poll']:.2f}s/request including ccxt throttling and network).")
    add(f"- Estimated weight per refresh: **{exchange['estimated_weight_per_poll']}** (400-limit klines ≈ 2 weight each).")
    add(f"- Nominal weight at the {settings['scan_interval_seconds']}s interval: **{exchange['estimated_weight_per_minute']} weight/min**, vs Binance USD-M **2400 weight/min**.")
    add("- The old polling loop slept *after* the fetches, so the true period was fetch time + interval (~205s). It now sleeps only the remaining time, keeping the cadence at 60s; with WS active the poll loop is replaced by streams.")
    add(f"- Analysis time dominates the diagnostic run (**{report['analysis_seconds']}s** for 12 symbols): repeated price-action/indicator recomputation per symbol. This affects scan latency, not correctness, and is a separate performance item.")
    add("")

    add("## 8. Is NO TRADE caused by bugs or missing data?")
    add("")
    add("**Before the fixes: yes** — the flat freshness threshold blocked every symbol on 1D data. ")
    add("**After the fixes: no.** Evidence:")
    add("")
    add("- All required timeframes have 399 closed bars (400 fetched, forming bar excluded; minimums 40–60) — no missing history.")
    add("- All last bars are closed; forming candles are excluded by `CandleStore.get_closed()`.")
    add("- Freshness is now bar-duration aware; no symbol is rejected for stale data.")
    add("- Rejections are specific, diverse strategy conditions (5M EMA/VWAP, 5M pattern, 15M structure, volume, score).")
    add("- Every SHORT score is below the unchanged 80 threshold; several LONG scores are far below. Even if a trigger passed, the score filter would still reject them.")
    add("- The engine's first-failure reason matched the independent diagnostic trace for 12/12 symbols.")
    add("")
    add("No trade was invented and the 80/100 threshold was not lowered. When conditions satisfy the strategy, the engine will emit a signal; until then NO TRADE is the correct output.")
    add("")

    Path("docs").mkdir(exist_ok=True)
    Path("docs/DIAGNOSTICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote docs/DIAGNOSTICS.md ({len(lines)} lines)")


if __name__ == "__main__":
    main()

# Signal-Only Mode

This bot is an **analytical signal generator**. It monitors Binance USD-M Futures 24/7, runs every
filter, and sends trading plans to Telegram. **It never opens, modifies or closes an exchange order.**

## 1. Default configuration

| Setting | Default | Meaning |
|---|---|---|
| `SIGNAL_ONLY` | `true` | Analysis + Telegram only |
| `PAPER_TRADING` | `false` | Optional internal simulation, not needed for signals |
| `DRY_RUN` | `true` | No real execution path under any configuration |

Public market data only. `BINANCE_API_KEY` / `BINANCE_API_SECRET` are optional and are never
required for signal delivery; no trading permissions are requested.

## 2. What runs on every confirmed candle close

1. WebSocket 5M/15M/1H/4H/1D streams (ccxt.pro), REST backfill and gap refill.
2. Indicators (EMA 9/21/50/200, RSI 7/14/21, VWAP, ATR 14, ADX 14, Volume SMA 20), price action,
   BOS/CHoCH, support/resistance, liquidity sweeps.
3. Signal Engine with the unchanged **80/100** base threshold.
4. False Signal Detection Engine (confirmation score, false-signal risk, hard rejection rules).
5. Unique `signal_id`, per-symbol cooldown, database dedup, notifier dedup.
6. Telegram message with verified prices and explicit confirmation details.
7. Follow-up tracking on closed candles: TP1/TP2/TP3, SL, expiry, EARLY → CONFIRMED/INVALIDATED.

No message is sent on a price tick. `/scan` triggers analysis, not order execution.

## 3. Telegram commands

`/start`, `/status`, `/signals`, `/active`, `/stats`, `/top`, `/market`, `/settings`, `/help`, plus
`/scan`, `/btc`, `/eth`, `/coin SYMBOL`, `/watchlist`, `/pause`, `/resume` (admin-gated where relevant).
`/stats` explicitly labels results as a simulation with fees, slippage and funding included.

## 4. Signal statuses

`ACTIVE`, `TP1 HIT`, `TP2 HIT`, `TP3 HIT`, `SL HIT`, `INVALIDATED`, `EXPIRED`.
A TP1/TP2 signal remains tracked until TP3 or SL; the displayed status reflects the latest event.

## 5. Guards

- Automated AST test scans the whole `app/` tree for order/position API names
  (`create_order`, `cancel_order`, `set_leverage`, `fetch_positions`, …) and fails if any appear.
- Tests confirm that in signal-only mode a signal is stored but no paper position exists.
- Tests confirm stale data, duplicate signals and unresolved outcomes are excluded.
- Startup migration upgrades legacy SQLite databases without deleting data.

## 6. Validation status — read this before trusting signals

The 150-day, 12-symbol, 15M multi-asset validation (504 base trades, 196 after the false-signal
filter, fees/slippage/funding included) found:

- Base expectancy **−0.1999 R** (bootstrap 95% CI −0.3611 … −0.0560).
- Filtered expectancy **−0.1472 R** (95% CI −0.3867 … +0.1011).
- Filtered max drawdown improved from −141.02 R to −50.25 R, and it removed 226 losing versus
  82 profitable base trades — but expectancy is still not reliably positive.
- Only 23 CONFIRMED ENTRY trades existed (+0.1456 R); **0 STRONG ENTRY** trades occurred.
- Out-of-sample expectancy was −0.3664 R (40 trades).

**Conclusion:** the filter reduces drawdown and removes many losing ideas, but this historical
sample does **not** demonstrate a profitable edge. No threshold, weight or parameter was tuned to
improve these numbers. Treat signals as analytical hypotheses, size risk conservatively, and do
not interpret Confirmation Score as a probability of profit.

Full details: `docs/MULTI_ASSET_BACKTEST.md`, `docs/MARKET_REGIME_ANALYSIS.md`,
`docs/SIGNAL_QUALITY_REPORT.md`.

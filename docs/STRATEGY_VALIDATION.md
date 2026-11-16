# Strategy & Paper-Trading Validation Report

Read-only validation of the **unchanged** trading rules. No parameter was tuned, the score
threshold stayed at **80/100**, and no live/real order path exists.

Reproduce: `python -m scripts.validate_strategy` and `python -m scripts.validate_paper_trading`.

## 1. Rule and scoring checks — 34/34 passed

| Area | Check | Result |
|---|---|---|
| Scoring contract | Component maxima sum to 100 (20+15+15+15+10+10+10+5) | PASS |
| Scoring contract | 100 → Excellent, 90 → Excellent, 80 → Strong, 70 → Moderate, 69 → Ignore | PASS |
| Scoring contract | Each component changes the total by exactly its own cap | PASS (8/8) |
| Threshold | `min_signal_score` still 80 | PASS |
| RSI engine | Classic Wilder reference 70.46 on the standard 15-close series | 70.4641 |
| Divergences | Pivots require `order` neighbours; last bar cannot be a pivot | PASS |
| Candles | Only closed bars reach analysis; forming bar excluded by store | PASS (10 stored → 9 used) |
| Candles | Pattern strength ∈ [0,1] and context flag present | PASS |
| Structure | BOS/CHoCH emitted only after a confirming close | PASS (unit tests) |
| Support/resistance | Clustered from historical swing reactions, side checked | PASS (unit tests) |
| Volume | RV = last volume / SMA20 of prior bars | 3.00 on the control case |
| Engine | Live symbols produce either a valid signal or a specific NO TRADE reason | PASS (4/4 sampled) |
| Causality | Full-frame vs prefix indicators at bar i | max diff **0.000e+00** on all 5 TFs |
| Cache | Cached vs freshly computed indicators and price action | max diff **0.000e+00** |
| Backtest | Walk-forward engine runs without error | PASS |

### Independent verification of score influence

`score_setup()` was exercised with controlled inputs and the resulting totals were compared with
the documented weights. Every component's contribution matched its specified maximum exactly:
MTF 20, RSI 15, candlestick 15, structure 15, S/R 10, volume 10, EMA/VWAP 10, volatility 5.
The sent/not-sent decision still uses the same hard filters first — the score never overrides an
invalid stop, insufficient RR, stale data or missing trigger.

## 2. No look-ahead / leakage

- Indicators are causal: for every timeframe, the value at bar `i` computed from the full frame
  equals the value at the last bar of `frame[:i+1]` (difference 0.000e+00).
- The backtester uses `IndicatorViewAt` for historical indicator values and rebuilds price action
  from `frame[:i+1]`; entry occurs at bar `i+1` **open**.
- The live engine receives only `CandleStore.get_closed()`, which excludes the forming bar, and
  additionally rejects `closed=False` bars.
- Pivot-based divergence detection cannot use the last `order` bars.
- The new per-frame caches are guarded by object identity and a content fingerprint, so no data
  leaks between symbols or timeframes.

## 3. Backtest — honest results

Walk-forward split: in-sample 50%, validation 25%, out-of-sample 25%. Costs, slippage, funding and
conservative same-bar SL priority are included. No optimisation was performed.

| Segment | Trades | Wins | Losses | Win rate | Expectancy | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| In-sample | 0 | 0 | 0 | 0.0% | 0.000 R | 0.000 R |
| Validation | 1 | 1 | 0 | 100.0% | +2.794 R | 0.000 R |
| Out-of-sample | 0 | 0 | 0 | 0.0% | 0.000 R | 0.000 R |
| Overall | 1 | 1 | 0 | 100.0% | +2.794 R | 0.000 R |

**Interpretation:** one trade is not statistically meaningful. 100% win rate and an infinite
profit factor on a single trade are reported as-is, not presented as evidence of profitability.
Zero-trade segments are reported as zero, not filled with invented statistics.

## 4. Paper trading validation

Deterministic scenarios (synthetic candles, fixed known paths), using the real
`PaperTradingEngine`, `SignalTracker` and `CostModel`:

| Scenario | Events | Closed | Win rate | Expectancy | Max DD | Fees |
|---|---|---:|---:|---:|---:|---:|
| Long, SL before TP | SL | 1 | 0.0% | −1.0850 R | −1.0850 R | 0.4250 USDT |
| Long, TP1 then SL | TP | 1 | 0.0% | −0.0850 R | −0.0850 R | 0.4250 USDT |
| Long, straight to TP3 | TP | 1 | 100.0% | +2.9150 R | 0.0000 R | 0.4250 USDT |
| Long, SL and TP in same bar | SL | 1 | 0.0% | −1.0850 R | −1.0850 R | 0.4250 USDT |
| Short, SL before TP | SL | 1 | 0.0% | −1.0850 R | −1.0850 R | 0.4250 USDT |

Verified behaviours:

- **Chronology:** a stop reached before any target is always a loss; a same-bar SL+TP resolves as
  SL (worst case). TP1 followed by the stop gives breakeven gross (−fees net).
- **Targets:** TP1 = 1R, TP2 = 2R, TP3 = 3R or next structural level; the engine tracks each level.
- **Costs:** taker + maker fees, 2× slippage and pro-rated funding are subtracted from realised R.
- **Risk:** fixed fractional sizing (0.5% default), no martingale, margin capped by balance.
- **Shorts:** mirrored stop/target geometry with identical accounting.

Historical replay of the single strategy-generated backtest trade:

| Backtest trades | Backtest outcome | Paper closed | Paper win rate | Paper expectancy | Paper max DD |
|---:|---|---:|---:|---:|---:|
| 1 | TP3 | 1 | 100.0% | +2.784 R | 0.000 R |

The 0.010 R difference vs the backtest (+2.794 R) comes from reconstructing the position size and
holding-time funding assumption from the recorded trade; it is disclosed rather than hidden.
As with the backtest, a single replay is a mechanics check, not a performance claim.

## 5. Continuous scanning validation

- WebSocket capability probe now targets `ccxt.pro`; live stream test succeeded, 60 streams active.
- Simulated disconnect test confirms reconnection and buffer update.
- 16-second live scheduler run: `feed_healthy True`, scan completed, no exceptions.
- Scans are triggered by new closed 5M candles, manual requests, or the 60 s interval — not by
  price updates. A per-symbol 240-minute cooldown plus deterministic signal IDs prevents duplicate
  ideas and duplicate Telegram messages.
- Telegram formatting and duplicate suppression remain covered by unit tests.

## 6. Limitations

- Strategy performance on this sample is **not** established: only one backtest trade occurred.
- No parameter was optimised; no in-sample tuning was performed.
- Live NO TRADE outcomes remain legitimate strategy verdicts; the threshold was not lowered.
- Paper trading is the only execution mode; real orders are never sent.

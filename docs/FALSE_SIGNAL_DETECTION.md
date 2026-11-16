# False Signal Detection Engine

Independent, add-on quality gate for the Crypto Futures Signal Bot. It **does not** replace the
base strategy, does **not** change the Signal Score threshold (80/100), and never opens orders.

Source: `app/false_signal/`. Integration point: `app/signal_engine/engine.py` after the base
score filter.

## 1. Why it exists

A base signal can be technically valid yet still be a false breakout, a liquidity trap, an
exhausted impulse or a low-participation move. This module answers eight questions explicitly:

1. Is the direction really confirmed?
2. Is the breakout genuine?
3. Is there liquidity-trap evidence?
4. Do closed candles confirm the move?
5. Does RSI agree with price?
6. Is volume participation sufficient?
7. Do higher and lower timeframes agree?
8. Is the entry late, early or already lost?

## 2. Components

| Component | File | Main outputs |
|---|---|---|
| False Breakout Detector | `false_breakout.py` | `CONFIRMED BREAKOUT`, `FAILED BREAKOUT`, `BREAKOUT RETEST`, `LIQUIDITY SWEEP`, `STOP HUNT CANDIDATE`, `NO BREAKOUT` |
| Liquidity Trap Detector | `liquidity_trap.py` | sweep high/low, equal highs/lows, false support/resistance break, long wick, rapid reversal, volume spike without continuation, failed retest + weighted strength |
| RSI Confirmation | `rsi_confirmation.py` | bullish/bearish confirmation, divergence warning, momentum weakness, false breakout warning, agreement −1..+1 |
| Candlestick Confirmation | `candle_confirmation.py` | closed-bar check, body quality, volume, direction match, proximity to level, next-bar follow-through |
| Volume Confirmation | `volume_confirmation.py` | relative volume, spike, expansion, divergence, breakout volume, rejection volume, weak participation |
| MTF Confirmation | `mtf_confirmation.py` | full/partial alignment, timeframe conflict, countertrend, trend-reversal candidate |
| Entry Quality | `entry_quality.py` | `GOOD ENTRY ZONE`, `LATE ENTRY`, `EARLY ENTRY`, `WAIT FOR RETEST`, `ENTRY INVALIDATED` |
| Scoring & Hard Rules | `scoring.py` | Confirmation Score, False Signal Risk, exact blocking reasons |
| Orchestrator / Recheck | `engine.py` | `ConfirmationVerdict`, post-close recheck state machine |

All indicators, candles, price action and pivot calculations are **reused** from existing cached
utilities (`IndicatorSet.from_frame`, `analyze_price_action`, `detect_divergences`,
`detect_patterns`, `frame_to_candles`). No duplicate indicator math was introduced.

## 3. Verdicts

| Verdict | Meaning | Sent to Telegram? |
|---|---|---|
| STRONG ENTRY | Confirmation ≥90 and risk ≤25 | Yes |
| CONFIRMED ENTRY | Confirmation ≥80 and risk ≤40 | Yes |
| EARLY ENTRY | Confirmation ≥70, risk ≤60; requires recheck | Yes, explicitly marked early |
| WEAK SIGNAL | Confirmation <70 or excessive risk | No — detailed rejection note |
| FALSE BREAKOUT | Confirmed failed breakout | No — detailed rejection note |
| LIQUIDITY TRAP | Strong trap (strength ≥0.6) | No — detailed rejection note |
| INVALIDATED | Entry already lost | No |
| NO TRADE | Other blocking condition | No |

**Confirmation Score is not a probability of profit.** Both 80/100 thresholds are initial
engineering categories, not statistically proven edge.

## 4. Hard rejection rules

A signal is blocked regardless of score when any of these is true. The exact reason is always
reported:

- confirmed false breakout;
- strong liquidity trap;
- critical higher-timeframe conflict;
- no closed candle available;
- stale market data (timeframe-aware freshness);
- entry already invalidated;
- stop distance structurally invalid (>4× ATR);
- Risk/Reward below the configured minimum.

The base engine's original 80/100 threshold is still applied **first**. The new gate is extra.

## 5. Confirmation Score (0–100)

| Component | Max |
|---|---:|
| Multi-timeframe agreement | 20 |
| Price Action confirmation | 15 |
| RSI confirmation | 15 |
| Candle confirmation | 15 |
| Volume confirmation | 10 |
| Breakout/retest quality | 10 |
| Entry location | 10 |
| Volatility suitability | 5 |

Categories: 90–100 STRONG, 80–89 CONFIRMED, 70–79 EARLY/WAIT, <70 WEAK.

### False Signal Risk (0–100) — separate metric

Contributors: failed breakout (35), strong trap (25), RSI divergence warning (15), momentum
weakness (8), candle mismatch (12), weak volume (12), volume divergence (8), timeframe conflict
(20), countertrend (10), late/invalidated entry (12), insufficient RR (10), overextension (8).
Capped at 100. Categories: 0–20 Low, 21–40 Moderate, 41–60 Elevated, 61–80 High, 81–100 Very High.

## 6. Closed-bar and look-ahead guarantees

- Every detector filters `candle.closed == True` before analysis.
- `FalseSignalEngine.evaluate` additionally drops unclosed rows from every supplied frame.
- All higher-timeframe frames in the comparative backtest are built from **complete** bar groups
  and sliced to the decision bar before evaluation.
- `find_divergences` relies on pivots confirmed by neighbouring bars.
- Regression test: adding an unclosed bar with extreme volume to a frame does **not** change the
  verdict (`test_engine_ignores_unclosed_candle_in_frame`).

## 7. Comparative historical test — actual results

Command: `python -m scripts.backtest_false_signal` (BTCUSDT 15M, 1000 bars, walk-forward splits,
fees/slippage/funding included, SL/TP chronology preserved).

| Metric | Base strategy | Base + False Signal Detection |
|---|---:|---:|
| Trades | 7 | 3 |
| Wins / losses | 4 / 3 | 2 / 1 |
| Win rate | 57.14% | 66.67% |
| Profit factor | 2.425 | 4.628 |
| Expectancy | +0.7298 R | +1.4364 R |
| Average R | +0.7298 R | +1.4364 R |
| Max drawdown | −2.3687 R | −1.1878 R |
| Total R | +5.1088 R | +4.3093 R |

Filtered ideas (4 of 7): 2× WEAK SIGNAL (late entry), 1× LIQUIDITY TRAP (strength 0.65),
1× FALSE BREAKOUT (failed breakout at level). Verdict distribution: 1 CONFIRMED ENTRY,
2 EARLY ENTRY, 2 WEAK SIGNAL, 1 LIQUIDITY TRAP, 1 FALSE BREAKOUT.

**Interpretation limits:** seven trades is a tiny sample. Higher win rate and expectancy here are
observations, not proof of robustness. Filters were **not** tuned to improve this historical win
rate; categories and weights were set before the run. Lower total R simply reflects fewer trades.
Walk-forward split metrics and the full filtered-detail list are stored in
`data/false_signal_backtest.json` (git-ignored runtime artefact).

## 8. Tracking

`SignalRecord` stores confirmation score, false signal risk, status, reasons, entry location and
countertrend flag. Rejected ideas are stored in `RejectionRecord`. Statistics expose win rate,
expectancy and profit factor by confirmation status, countertrend subset, false breakout rate and
liquidity trap rate. No conclusion about category accuracy should be drawn from a small sample.

## 9. Testing

114 tests pass, including unit tests for every detector, scoring categories, hard rules,
state transitions, no-look-ahead, and an integration test covering evaluation → Signal → SQLite →
statistics → Telegram formatting.

## 10. Reproduce

```bash
python -m pytest -q
python -m scripts.backtest_false_signal
```

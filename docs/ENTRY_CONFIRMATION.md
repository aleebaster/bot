# Entry Confirmation & Post-Signal Recheck

This document explains how the bot decides **whether to enter now or wait**, and what happens to
an `EARLY ENTRY` after the next candle closes.

## 1. The eight questions the bot must answer

| Question | Component / field |
|---|---|
| Why enter now? | `reasons_confirm` in the signal message |
| What confirmations exist? | Confirmation Score components (MTF / PA / RSI / candle / volume / breakout / entry / volatility) |
| Any false breakout signs? | `FalseBreakoutResult.verdict` + `breakout` score contribution |
| Any liquidity trap signs? | `LiquidityTrapResult.strength` and findings |
| Is the entry late? | `EntryQualityResult.location`, `impulse_consumed_pct`, `extension_atr` |
| What is the false-signal risk? | `FalseSignalRisk.score` and category (separate from Confirmation Score) |
| What invalidates the idea? | `invalidation` price + hard-block reasons |
| Enter now or wait? | `EntryVerdict`: STRONG / CONFIRMED / EARLY / WEAK / FALSE BREAKOUT / LIQUIDITY TRAP / INVALIDATED / NO TRADE |

## 2. Entry location rules

`entry_quality.py` compares the last **closed** 5M price with the planned entry, ATR(15M), EMA21,
recent swing extremes and planned TP1:

- `ENTRY_INVALIDATED` — price already passed TP1 or breached the stop. Blocked.
- `LATE_ENTRY` — more than 60% of the impulse toward TP1 already consumed, or price >2.5 ATR from
  EMA21. Penalised, frequently rejected.
- `EARLY_ENTRY` — price more than 0.8 ATR away from the planned entry zone. Requires recheck.
- `WAIT_FOR_RETEST` — price sits in the middle of a range (nearest level >1 ATR away).
- `GOOD_ENTRY_ZONE` — price near the planned zone with structural confirmation.

Distance, extension, R-multiple stop and RR are all recorded in the message and database.

## 3. Post-signal recheck state machine

`FalseSignalEngine.recheck()` is called after a **new closed candle** appears (the scheduler already
detects new closed 5M bars and triggers a scan). Rules:

1. `EARLY ENTRY` is never reported as confirmed at creation time.
2. On the next closed bar, the engine re-evaluates direction, level retention, RSI, volume and
   structure using only closed candles.
3. If Confirmation Score ≥80 and False Signal Risk ≤40 → `CONFIRMED_ENTRY`.
4. If any hard block appears or the score collapses → `INVALIDATED`.
5. Otherwise it remains `EARLY_ENTRY`.

Historical trade outcomes are **never rewritten**. A recheck only changes the forward-looking
confirmation status; TP/SL results and realized R stay as originally recorded.

## 4. Telegram format (real computed values only)

Approved signals include an `ENTRY QUALITY` block:

```
🧠 ENTRY QUALITY
Confirmation Score: 91.0/100
False Signal Risk: 12.0/100

Status: STRONG ENTRY

✅ Trend Alignment
✅ RSI Confirmation
✅ Candlestick Confirmation
✅ Volume Confirmation
✅ Breakout / Retest
✅ Entry Zone Valid

⚠️ RISK CHECK
Risk/Reward: 1:2.50
Stop Distance: ...
ATR: ...
Invalidation Level: ...

Decision: ENTRY CONFIRMED
```

Rejected ideas get a separate, specific message:

```
⚠️ SIGNAL REJECTED
Symbol: ETHUSDT
Direction: LONG

Reason:
- False breakout detected.
- RSI momentum disagreement.
- Weak volume confirmation.

False Signal Risk: 78/100
Decision: NO TRADE.
```

No generic `NO TRADE` is used when a concrete blocking reason exists. Notifier dedup prevents the
same rejection from being sent repeatedly.

## 5. Countertrend handling

Countertrend setups are **not automatically rejected**. They receive a lower MTF component and a
risk contributor, are labelled `countertrend=True`, and are stored separately in statistics
(`countertrend` block: signals, win rate, expectancy, profit factor, max drawdown). This keeps them
auditable without hiding them.

## 6. What is deliberately NOT done

- No "confirmation probability" claim — both scores are engineering ratings.
- No threshold tuning on one historical window; the 80/100 base and the confirmation categories
  were fixed before the comparative backtest.
- No real orders, no API secrets in code, no use of forming candles.
- No silent rejection: every block carries a reason string.

## 7. Validation

114 automated tests pass, including the closed-bar look-ahead regression and the full
evaluation → persistence → statistics → Telegram integration flow. Historical comparison results
(base 7 trades vs filtered 3 trades) are reported honestly in `docs/FALSE_SIGNAL_DETECTION.md`
and are **not** presented as statistically conclusive.

# Trading Strategy, Scoring and Risk Methodology

This document is the specification implemented by the signal engine. It is written so that every
signal can be audited: each number below is computed from closed candles.

## 1. Guiding principle

The bot is a **quality filter**, not a signal factory. A signal is emitted only when the market
structure, momentum, volume, volatility and risk all agree. Otherwise the engine returns
`NO TRADE` with a machine-readable reason. Score is **not** a probability of profit.

## 2. Timeframe hierarchy

| Timeframe | Role |
|---|---|
| 1D | Global context / regime |
| 4H | Primary trend, BOS/CHoCH, structure levels |
| 1H | Trend confirmation, higher-timeframe liquidity |
| 15M | Setup search, entry-zone context, structural stop |
| 5M | Entry trigger, final volume and micro-structure confirmation |

Rules:

1. Only **closed** candles are used. The most recent forming bar is excluded by `CandleStore.get_closed()`.
2. Higher timeframes define the allowed direction. The engine never takes LONG against a bearish
   4H structure and never takes SHORT against a bullish one, unless a confirmed CHoCH exists.
3. 15M finds the setup; 5M must trigger it. A good 15M setup without a 5M trigger is not a signal.

## 3. Trend and structure

- **EMA stack**: bullish alignment requires `close > EMA21 > EMA50 > EMA200`; bearish is the inverse.
- **EMA200**: acts as the regime line. Price above it allows LONG ideas; below it allows SHORT ideas.
- **ADX 14**: trend-strength filter. `ADX >= 20` required to treat a directional move as a trend.
  ADX < 20 means "no trend / chop" → NO TRADE.
- **VWAP**: institutional reference. LONGs are preferred above VWAP, SHORTs below.
- **Swing points**: confirmed with `order` neighbouring bars. HH/HL = bullish structure,
  LH/LL = bearish structure.
- **BOS**: close beyond the last swing high/low in the direction of the trend.
- **CHoCH**: close beyond the last swing high/low **against** the prior structure — a possible reversal.
- **Support/resistance**: clusters of historical swing reactions (within 0.4% tolerance), weighted by
  the number of touches. Random price points are never used.
- **Liquidity sweep**: a wick takes out a swing level but the close returns inside it.
- **False breakout**: close back across a broken level; it invalidates the setup.

## 4. RSI engine

Wilder RSI is computed for periods 7, 14 and 21 with an SMA seed (verified against the classic
70.46 reference). The engine evaluates:

- 70/30 extremes, 50-level and 50-crosses, momentum (`RSI7` vs `RSI14`).
- Regular bullish (price LL / RSI HL), regular bearish (price HH / RSI LH).
- Hidden bullish (price HL / RSI LL), hidden bearish (price LH / RSI HH).
- Exits from overbought/oversold.

**Hard rule:** RSI < 30 alone is never a LONG trigger, and RSI > 70 alone is never a SHORT trigger.
Entering an already-extended impulse is penalised (> 3 ATR from EMA21).

## 5. Candlestick confirmation

Recognised: Bullish/Bearish Engulfing, Hammer, Shooting Star, Pin Bar, Morning/Evening Star,
Doji, Inside/Outside Bar, Three White Soldiers, Three Black Crows, Strong Rejection.

Each pattern contributes only when it appears in the correct location (after a pullback in an
uptrend for bullish patterns, after a rally in a downtrend for bearish ones). A pattern without
context is informational only.

## 6. Volume

Relative volume = last closed volume / SMA20 of the previous 20 volumes.

- `>= 1.5`: strong confirmation (and extra credit if it coincides with a breakout).
- `1.2 – 1.5`: acceptable.
- `< 1.0` on 5M or `< 0.8` on 15M: NO TRADE.
- A weak breakout is never confirmed by RSI or a single candle alone.

## 7. Signal score (0–100)

| Component | Max | What is rewarded |
|---|---:|---|
| Multi-timeframe trend | 20 | HTF alignment and ADX-weighted strength |
| RSI | 15 | 50-side, momentum, favourable divergence, extreme exit |
| Candlestick confirmation | 15 | Pattern strength on 15M + 5M, context confirmed |
| Market structure | 15 | Structure direction, BOS/CHoCH, sweep, retest |
| Support / resistance | 10 | Proximity to a historical reaction zone, zone strength |
| Volume | 10 | Relative volume and breakout confirmation |
| EMA / VWAP | 10 | VWAP side, EMA stack, EMA200 side |
| Volatility / entry quality | 5 | Stop distance 0.8–2.5 × ATR, not extended |

Categories: **Excellent 90–100**, **Strong 80–89**, **Moderate 70–79**, **Ignore < 70**.
Default send threshold: **80**.

### Hard filters override the score

A signal is rejected even with a high score if: data is stale, a forming candle is involved,
history is insufficient, structure/RSI/volume/EMA/VWAP triggers are missing, RR is below minimum,
the stop is structurally or volatility-invalid, expected TP1 reward does not cover costs, margin
exceeds balance, a false breakout is present, or the move is already exhausted.

## 8. Entry, stop and targets

- **Entry zone**: `5M close ± 0.15 × ATR(5M)`.
- **Stop loss**: the nearest 5M/15M swing invalidation level, clamped to `0.8–2.5 × ATR(15M)`.
  A stop closer than `0.3 × ATR` or further than `4 × ATR` is rejected.
- **TP1** = 1R, **TP2** = 2R, **TP3** = 3R or the next structural level beyond 3R (whichever is
  closer to price). Structural levels come from 15M and 1H reaction clusters.
- **RR** = reward to TP3 / risk; minimum 1:2.
- Every signal message lists why each target was chosen.

## 9. Risk management

```
risk_usdt   = balance × risk_per_trade          # default 0.5%
size        = risk_usdt / |entry − stop|
notional    = size × entry
margin      = notional / leverage
```

- Leverage changes margin, **never** risk. No martingale, no risk escalation after losses.
- Maximum concurrent ideas (default 3) enforced before opening a new paper position.
- Cost model: taker + maker fees, 2× slippage, and funding pro-rated by holding time.
  If expected TP1 reward ≤ estimated cost → NO TRADE.
- Account balance, risk, leverage and cost inputs are all configurable via `.env`.

## 10. Outcome tracking

Candles are walked in chronological order from the signal timestamp:

1. If SL and a TP are touched in the **same bar**, SL wins (worst-case assumption).
2. If SL is hit before any TP → outcome `SL`, realized **−1R net of fees**.
3. After TP1 the simulated stop moves to breakeven; after TP2 the result is locked at **+1R**.
4. TP3 closes the idea at **+3R** (or the structural R multiple).
5. MFE/MAE are recorded in R for every idea.
6. Expired signals are closed with no fabricated profit.

Statistics (total, win/loss rate, profit factor, expectancy, average R, max drawdown, long/short,
per-symbol, per-timeframe) are computed only from closed records. Empty databases report zeros.

## 11. Backtesting assumptions

- Decision at bar `i` uses bars `≤ i`; entry at bar `i+1` **open** (no look-ahead).
- Slippage and fees on entry and exit; funding accrues with holding time.
- Same-bar SL priority; no overlapping positions.
- Fixed parameters — **no optimisation**, so no in-sample curve fitting.
- In-sample 50% / validation 25% / out-of-sample 25% reported separately.
- All timeframes in the live engine; the standalone backtester derives higher-timeframe context
  only from fully closed aggregated groups of the supplied series (documented approximation).

## 12. Market filters (NO TRADE)

Low liquidity, absent trend/structure, choppy range, stale data, insufficient volume, invalid stop,
RR below minimum, already-completed setup, false breakout, or expected profit below costs.

## 13. Instrument universe

Default watchlist: BTC, ETH, BNB, SOL, XRP, DOGE, ADA, LINK, AVAX, NEAR, SUI, LTC (all USDT-M).
`ExchangeClient.get_top_liquid_symbols()` can extend it with the top 20 contracts by 24h quote
volume; leveraged tokens and inactive markets are excluded. The watchlist is editable via Telegram.

## 14. Safety

Public market data endpoints only. No withdrawals, no trading permissions, no real orders.
Secrets live only in `.env`, which is git-ignored. `.env.example` contains empty placeholders.

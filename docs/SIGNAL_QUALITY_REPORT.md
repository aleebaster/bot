# Signal Quality Report

Period 2026-06-19 → 2026-11-16 | base trades **504** | kept **196** | filtered **308**

## 1. Signal categories (all generated trades, including filtered)

Category performance below uses the outcome the base backtester recorded for every idea. Filtered ideas are shown for audit but are NOT sent as signals.

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| CONFIRMED ENTRY | 23 | 8 | 15 | 34.78 | 1.18 | 0.1456 | -8.7887 |
| EARLY ENTRY | 173 | 47 | 126 | 27.17 | 0.80 | -0.1861 | -45.9211 |
| FALSE BREAKOUT | 37 | 6 | 31 | 16.22 | 0.41 | -0.6172 | -22.8360 |
| LIQUIDITY TRAP | 3 | 0 | 3 | 0.00 | 0.00 | -1.1933 | -3.5799 |
| STRONG ENTRY | 0 | 0 | 0 | 0.00 | 0.00 | 0.0000 | 0.0000 |
| WEAK SIGNAL | 268 | 76 | 192 | 28.36 | 0.82 | -0.1697 | -71.6029 |

Categories with **zero** occurrences in this sample: STRONG ENTRY. No performance conclusion is possible for them.

## 2. LONG vs SHORT (kept signals)

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| LONG | 107 | 31 | 76 | 28.97 | 0.86 | -0.1220 | -28.5261 |
| SHORT | 89 | 24 | 65 | 26.97 | 0.81 | -0.1775 | -33.7696 |

### Per-symbol direction detail

| Symbol | Direction | Trades | WR % | Expectancy R | Max DD R |
|---|---|---|---|---|---|
| BTCUSDT | SHORT | 12 | 33.33 | 0.069 | -3.806 |
| BTCUSDT | LONG | 16 | 25.00 | -0.365 | -8.499 |
| ETHUSDT | LONG | 17 | 52.94 | 0.795 | -5.242 |
| ETHUSDT | SHORT | 4 | 50.00 | 0.727 | -2.537 |
| BNBUSDT | LONG | 12 | 16.67 | -0.776 | -9.947 |
| BNBUSDT | SHORT | 6 | 33.33 | -0.053 | -4.550 |
| SOLUSDT | LONG | 13 | 30.77 | 0.009 | -6.147 |
| SOLUSDT | SHORT | 4 | 25.00 | -0.201 | -3.683 |
| XRPUSDT | SHORT | 13 | 30.77 | -0.040 | -5.033 |
| XRPUSDT | LONG | 4 | 50.00 | 0.703 | -1.307 |
| DOGEUSDT | SHORT | 11 | 27.27 | -0.195 | -7.908 |
| DOGEUSDT | LONG | 3 | 33.33 | 0.023 | -2.826 |
| ADAUSDT | SHORT | 7 | 0.00 | -1.191 | -8.339 |
| ADAUSDT | LONG | 2 | 0.00 | -1.119 | -2.238 |
| LINKUSDT | LONG | 13 | 23.08 | -0.308 | -8.629 |
| LINKUSDT | SHORT | 6 | 16.67 | -0.550 | -6.150 |
| AVAXUSDT | LONG | 8 | 25.00 | -0.180 | -4.730 |
| AVAXUSDT | SHORT | 2 | 50.00 | 0.758 | -1.326 |
| NEARUSDT | SHORT | 5 | 40.00 | 0.454 | -2.318 |
| SUIUSDT | SHORT | 14 | 28.57 | -0.099 | -8.149 |
| SUIUSDT | LONG | 6 | 16.67 | -0.558 | -3.566 |
| LTCUSDT | SHORT | 5 | 0.00 | -1.304 | -6.518 |
| LTCUSDT | LONG | 13 | 23.08 | -0.262 | -7.359 |

## 3. False Signal Detection effectiveness

- Profitable base trades removed by the filter: **82**
- Losing base trades removed by the filter: **226**
- Base expectancy: **-0.1999 R**
- Filtered expectancy: **-0.1472 R**
- Base max drawdown: **-141.0193 R**
- Filtered max drawdown: **-50.2468 R**

Stop-loss counts by category:

| Category | SL count |
|---|---|
| CONFIRMED ENTRY | 15 |
| EARLY ENTRY | 126 |
| FALSE BREAKOUT | 31 |
| LIQUIDITY TRAP | 3 |
| WEAK SIGNAL | 192 |

Most frequent rejection reasons:

| Reason | Count |
|---|---|
| Late entry - impulse largely consumed | 239 |
| Equal lows | 196 |
| Equal highs | 191 |
| RSI momentum disagreement | 56 |
| Long wick rejection | 55 |
| Volume spike without continuation | 31 |
| Sweep of previous high | 22 |
| Sweep of previous low | 21 |
| False resistance break | 18 |
| False support break | 17 |
| Confirmed false breakout: Wick sweep with rejection and volume spike - probable stop hunt | 9 |
| Failed retest | 6 |
| Stop hunt candidate | 3 |
| Strong liquidity trap (0.65): Sweep of previous low; Equal highs; Equal lows; Long wick rejection; Volume spike without continuation | 2 |
| Strong liquidity trap (0.95): Sweep of previous low; Equal lows; False support break; Stop hunt candidate; Long wick rejection; Volume spike without continuation | 2 |

A filter that removes profitable trades is not automatically bad: the relevant question is whether expectancy and drawdown improve, not win rate alone. Bootstrap intervals in docs/MULTI_ASSET_BACKTEST.md show the uncertainty of these estimates.

## 4. Limitations

- Category sample sizes are small; STRONG/CONFIRMED/EARLY counts may be single digits.
- No claim is made that category ratings are statistically calibrated probabilities.
- Statistics are computed from closed trades only; no open positions are fabricated.


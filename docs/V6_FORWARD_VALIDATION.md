# V6 Forward Validation — Independent Window

Window: **2026-01-01 → 2026-06-20** (15M, 12 symbols). This period ends BEFORE the previous V6 development sample (2026-06-21 → 2026-11-16).

Data integrity: REST pagination from a date before the window (7-day indicator warmup), only closed candles analysed, trades filtered to the window, unique signal IDs, identical fees/slippage/funding for both arms, decisions made only from prefixes ending at the decision bar.

## 1. Sample

| Metric | Value |
|---|---|
| V0 signals in window | 267 |
| V6 entered trades | 54 |
| EARLY signals | 241 |
| EARLY confirmed after next bar | 28 |
| EARLY invalidated | 170 |
| EARLY expired | 43 |

## 2. V0 vs V6

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| V0 production | 267 | 75 | 192 | 28.09 | 0.838 | -0.1472 | -65.575 | 27.34 | 71.54 |
| V6 entered | 54 | 13 | 41 | 24.07 | 0.716 | -0.2632 | -28.517 | 24.07 | 74.07 |
| V6 per original signal (zeros for skipped) | 267 | 13 | 41 | 4.87 | 0.716 | -0.0532 | -28.517 | 4.87 | 14.98 |

## 3. EARLY recheck economics

| Metric | Value |
|---|---|
| Avoided losing ideas | 152 |
| R avoided | -192.0379 |
| Trades worsened by delayed entry | 1 |
| Extra R lost to delay | -1.2484 |
| Average fee R on V6 entries | 0.1221 |
| Average entry shift (ATR) | -0.1682 |

## 4. Groups (V6 entered)

### Direction

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| LONG | 18 | 5 | 13 | 27.78 | 0.791 | -0.1967 | -11.555 | 27.78 | 72.22 |
| SHORT | 36 | 8 | 28 | 22.22 | 0.678 | -0.2964 | -16.962 | 22.22 | 75.00 |

### Symbol

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| ADAUSDT | 3 | 0 | 3 | 0.00 | 0.000 | -0.8196 | -2.459 | 0.00 | 66.67 |
| AVAXUSDT | 2 | 0 | 2 | 0.00 | 0.000 | -1.1928 | -2.386 | 0.00 | 100.00 |
| BNBUSDT | 5 | 3 | 2 | 60.00 | 2.878 | 1.0773 | -2.868 | 60.00 | 40.00 |
| BTCUSDT | 3 | 0 | 3 | 0.00 | 0.000 | -1.5222 | -4.566 | 0.00 | 100.00 |
| DOGEUSDT | 4 | 0 | 4 | 0.00 | 0.000 | -1.2182 | -4.873 | 0.00 | 100.00 |
| ETHUSDT | 6 | 3 | 3 | 50.00 | 2.050 | 0.6794 | -2.508 | 50.00 | 50.00 |
| LINKUSDT | 3 | 0 | 3 | 0.00 | 0.000 | -1.1619 | -3.486 | 0.00 | 100.00 |
| LTCUSDT | 7 | 1 | 6 | 14.29 | 0.364 | -0.7128 | -7.847 | 14.29 | 85.71 |
| NEARUSDT | 3 | 0 | 3 | 0.00 | 0.000 | -1.1144 | -3.343 | 0.00 | 100.00 |
| SOLUSDT | 8 | 4 | 4 | 50.00 | 2.386 | 0.8104 | -3.548 | 50.00 | 50.00 |
| SUIUSDT | 3 | 0 | 3 | 0.00 | 0.000 | -1.2196 | -3.659 | 0.00 | 100.00 |
| XRPUSDT | 7 | 2 | 5 | 28.57 | 0.934 | -0.0568 | -6.040 | 28.57 | 71.43 |

### Regime

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| bear | 23 | 5 | 18 | 21.74 | 0.654 | -0.3258 | -14.605 | 21.74 | 78.26 |
| bull | 5 | 0 | 5 | 0.00 | 0.000 | -1.2618 | -6.309 | 0.00 | 100.00 |
| sideways | 26 | 8 | 18 | 30.77 | 0.982 | -0.0157 | -13.000 | 30.77 | 65.38 |

### Volatility

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| high | 14 | 4 | 10 | 28.57 | 0.977 | -0.0189 | -6.985 | 28.57 | 71.43 |
| low | 17 | 4 | 13 | 23.53 | 0.624 | -0.3803 | -9.912 | 23.53 | 76.47 |
| normal | 23 | 5 | 18 | 21.74 | 0.651 | -0.3253 | -17.428 | 21.74 | 73.91 |

### Split

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| first_third | 23 | 9 | 14 | 39.13 | 1.409 | 0.3110 | -7.152 | 39.13 | 60.87 |
| out_of_sample | 17 | 2 | 15 | 11.76 | 0.318 | -0.7135 | -12.129 | 11.76 | 82.35 |
| second_third | 14 | 2 | 12 | 14.29 | 0.377 | -0.6598 | -14.830 | 14.29 | 85.71 |

### Confirmation Score

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| 70-79 | 0 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| 80-89 | 28 | 7 | 21 | 25.00 | 0.776 | -0.1997 | -15.128 | 25.00 | 71.43 |
| 90+ | 26 | 6 | 20 | 23.08 | 0.656 | -0.3315 | -17.179 | 23.08 | 76.92 |

### False Signal Risk

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| Elevated | 0 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| High | 0 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| Low | 15 | 5 | 10 | 33.33 | 1.099 | 0.0826 | -7.833 | 33.33 | 66.67 |
| Moderate | 39 | 8 | 31 | 20.51 | 0.589 | -0.3962 | -26.642 | 20.51 | 76.92 |

### Next-bar verdict

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| CONFIRMED ENTRY | 4 | 2 | 2 | 50.00 | 2.205 | 0.7685 | -2.551 | 50.00 | 50.00 |
| EARLY ENTRY | 24 | 5 | 19 | 20.83 | 0.614 | -0.3611 | -12.577 | 20.83 | 75.00 |
| FALSE BREAKOUT | 15 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| LIQUIDITY TRAP | 3 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| None | 43 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| WEAK SIGNAL | 152 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |

### Status

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| ENTERED | 28 | 7 | 21 | 25.00 | 0.776 | -0.1997 | -15.128 | 25.00 | 71.43 |
| EXPIRED | 43 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |
| INVALIDATED | 170 | 0 | 0 | 0.00 | 0.000 | 0.0000 | 0.000 | 0.00 | 0.00 |

## 5. Limitations

- Groups with fewer than ~30 trades are descriptive only.
- The whole window is OOS relative to V6 development; internal thirds are diagnostic splits.
- Zero-R outcomes for skipped ideas are not losses: they represent opportunities not taken.
- No parameter was tuned on this window; V6 remains experimental unless all criteria pass.

## Conclusion

On this independent window V6 entered **54** trades with expectancy **-0.2632 R**, PF **0.716** and OOS expectancy **-0.7135 R** — worse than V0 on expectancy, PF and OOS. The forward test does **not** support promoting V6. Keep it experimental and do not enable it for live Telegram signals.

# V6 vs Baseline — Forward Window

V0: 267 signals, E[R] -0.1472, PF 0.838, MaxDD -65.575.
V6: 54 entries, E[R] -0.2632, PF 0.716, MaxDD -28.517.

## Bootstrap 95% CI (expectancy)

| Arm | N | Mean | CI low | CI high |
|---|---|---|---|---|
| V0 | 267 | -0.1472 | -0.3661 | 0.0661 |
| V6 | 54 | -0.2632 | -0.6950 | 0.2164 |
| V6 per original signal | 267 | -0.0532 | -0.1441 | 0.0412 |

## Direction

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| V0 LONG | 78 | 21 | 57 | 26.92 | 0.788 | -0.1960 | -32.686 | 26.92 | 73.08 |
| V0 SHORT | 189 | 54 | 135 | 28.57 | 0.859 | -0.1271 | -38.624 | 27.51 | 70.90 |

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| V6 LONG | 18 | 5 | 13 | 27.78 | 0.791 | -0.1967 | -11.555 | 27.78 | 72.22 |
| V6 SHORT | 36 | 8 | 28 | 22.22 | 0.678 | -0.2964 | -16.962 | 22.22 | 75.00 |

## Regime

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| V6 bear | 23 | 5 | 18 | 21.74 | 0.654 | -0.3258 | -14.605 | 21.74 | 78.26 |
| V6 bull | 5 | 0 | 5 | 0.00 | 0.000 | -1.2618 | -6.309 | 0.00 | 100.00 |
| V6 sideways | 26 | 8 | 18 | 30.77 | 0.982 | -0.0157 | -13.000 | 30.77 | 65.38 |

## Success criteria

| Criterion | Pass |
|---|---|
| Expectancy > 0 | NO |
| Profit factor > 1 | NO |
| Max DD better than V0 | YES |
| Bootstrap CI lower bound > 0 | NO |
| OOS expectancy > 0 | NO |
| Sufficient trade count (>= 100) | NO |
| No single symbol dominates (>40% of trades) | YES |

**Verdict: criteria NOT fully met — keep V6 experimental.**

Fees, slippage and funding are identical in both arms. Win rate alone is not a success criterion.

The shallower V6 drawdown is partly a mechanical consequence of trading 54 times instead of 267; per-trade expectancy, PF and OOS all deteriorated, so it must not be read as an improvement.

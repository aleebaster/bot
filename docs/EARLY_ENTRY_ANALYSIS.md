# EARLY ENTRY Analysis

EARLY ENTRY trades: **171** (88.1% of kept signals).

An EARLY ENTRY was emitted when Confirmation Score was 70–79 with acceptable risk. The experiment waits for the NEXT closed 5M bar, re-runs the same filter, and enters at the following bar open if the verdict becomes CONFIRMED/STRONG. No historical outcome is rewritten.

## Original outcomes grouped by next-bar verdict (descriptive only)

These are the ORIGINAL trade results, split by what the next-bar recheck would have decided. They are not the simulated results after waiting.

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| CONFIRMED ENTRY | 2 | 1 | 1 | 50.00 | 2.434 | 0.8375 | -1.168 | 50.00 | 50.00 |
| EARLY ENTRY | 32 | 17 | 15 | 53.12 | 2.487 | 0.8586 | -5.246 | 53.12 | 46.88 |
| FALSE BREAKOUT | 9 | 2 | 7 | 22.22 | 0.603 | -0.3803 | -6.086 | 22.22 | 77.78 |
| LIQUIDITY TRAP | 2 | 1 | 1 | 50.00 | 1.960 | 0.6031 | -1.257 | 50.00 | 50.00 |
| WEAK SIGNAL | 126 | 30 | 96 | 23.81 | 0.674 | -0.3192 | -45.965 | 23.81 | 76.19 |

## Confirmation delay and entry price

- Approved after next bar: **34/171**
- Average entry shift: **0.0827 ATR**
- Average shift when approved: **0.3673 ATR**
- Original expectancy of all EARLY trades: **-0.0777 R**
- Original expectancy of the 34 later-approved subset: **0.8573 R**
- Projected expectancy of those 34 after waiting (entry slippage included): **0.5044 R**
- Original expectancy of the 137 skipped ideas: **-0.3097 R**
- Average expectancy across all EARLY ideas with skipped ideas counted as 0: **0.1003 R**
- Losses avoided by waiting: **104**
- New losses created by waiting: **3**

## Missing confirmations (rejection reason frequency among EARLY trades)

| Group | N | Wins | Losses | WR % | PF | E[R] | MaxDD | TP3 % | SL % |
|---|---|---|---|---|---|---|---|---|---|
| Equal highs | 106 | 31 | 75 | 29.25 | 0.860 | -0.1288 | -20.193 | 29.25 | 70.75 |
| Equal lows | 94 | 24 | 70 | 25.53 | 0.711 | -0.2821 | -35.296 | 25.53 | 74.47 |
| Failed retest | 3 | 2 | 1 | 66.67 | 4.364 | 1.2995 | -1.159 | 66.67 | 33.33 |
| Late entry - impulse largely consumed | 123 | 39 | 84 | 31.71 | 1.002 | 0.0019 | -18.341 | 31.71 | 68.29 |
| Long wick rejection | 22 | 11 | 11 | 50.00 | 1.948 | 0.6570 | -4.065 | 50.00 | 50.00 |
| RSI momentum disagreement | 12 | 5 | 7 | 41.67 | 1.566 | 0.3987 | -6.021 | 41.67 | 58.33 |
| Sweep of previous high | 15 | 6 | 9 | 40.00 | 1.500 | 0.3754 | -4.664 | 40.00 | 60.00 |
| Sweep of previous low | 11 | 3 | 8 | 27.27 | 0.777 | -0.2059 | -6.380 | 27.27 | 72.73 |
| Volume spike without continuation | 13 | 5 | 8 | 38.46 | 1.211 | 0.1722 | -6.953 | 38.46 | 61.54 |

## Conclusion

The gain comes mainly from NOT entering the 137 ideas that failed the next-bar recheck (their original expectancy was negative), not from a better entry price: the 34 approved ideas lost roughly 0.35 R to waiting slippage. Only 34/171 trades remained, so this is a hypothesis, not proof. See docs/STRATEGY_EXPERIMENTS.md variant V6 for OOS and bootstrap intervals.

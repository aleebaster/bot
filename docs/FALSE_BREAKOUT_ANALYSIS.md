# FALSE BREAKOUT Analysis

FALSE BREAKOUT ideas: **30** (winners 6, losers 24).

These ideas were filtered out; outcomes are shown only to audit whether the filter was justified.

## Feature comparison: winners vs losers

| Feature | Winners | Losers |
|---|---|---|
| N | 6 | 24 |
| Expectancy R | 2.7003 | -1.2706 |
| Avg relative volume | 2.684 | 2.429 |
| Avg ATR% | 0.00460 | 0.00500 |
| Avg entry extension (ATR) | 0.136 | 0.121 |
| Avg holding bars | 14.67 | 14.38 |
| Avg confirmation score | 65.50 | 63.79 |

## Rejection reason frequency

| Reason | Count |
|---|---|
| Late entry - impulse largely consumed | 23 |
| False resistance break | 14 |
| False support break | 14 |
| Equal highs | 12 |
| Equal lows | 11 |
| Long wick rejection | 10 |
| Confirmed false breakout: Wick sweep with rejection and volume spike - probable stop hunt | 7 |
| Volume spike without continuation | 5 |
| Stop hunt candidate | 4 |
| Sweep of previous low | 4 |
| RSI momentum disagreement | 2 |
| Strong liquidity trap (1.00): Sweep of previous low; Equal highs; Equal lows; False support break; Stop hunt candidate; Long wick rejection; Volume spike without continuation | 2 |
| Confirmed false breakout: FAILED BREAKOUT at 0.07131057 (bars since break=3) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 0.19261765 (bars since break=2) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 0.22298750 (bars since break=2) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 0.67763750 (bars since break=2) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.11441875 (bars since break=3) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.27920000 (bars since break=7) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.39225833 (bars since break=7) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.50081628 (bars since break=5) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.77433333 (bars since break=5) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1.98077143 (bars since break=5) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 12.43653571 (bars since break=4) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 1880.36550000 (bars since break=7) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 45.33071429 (bars since break=3) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 5.89200000 (bars since break=7) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 589.39611765 (bars since break=5) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 64.94000000 (bars since break=4) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 7.22660000 (bars since break=3) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 72.88750000 (bars since break=2) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 722.61744186 (bars since break=4) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 780.73421053 (bars since break=4) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 8.16116667 (bars since break=6) | 1 |
| Confirmed false breakout: FAILED BREAKOUT at 91.68714286 (bars since break=2) | 1 |
| Confirmed false breakout: STOP HUNT CANDIDATE at 2779.36857143 (bars since break=3) | 1 |
| Strong liquidity trap (0.60): Sweep of previous low; False support break; Stop hunt candidate | 1 |
| Strong liquidity trap (0.65): Equal highs; Equal lows; False support break; Long wick rejection; Volume spike without continuation | 1 |
| Strong liquidity trap (0.70): Sweep of previous low; Equal highs; False support break; Stop hunt candidate | 1 |
| Strong liquidity trap (0.75): Equal highs; False resistance break; Stop hunt candidate; Long wick rejection; Volume spike without continuation | 1 |
| Strong liquidity trap (0.75): Equal lows; False support break; Stop hunt candidate; Long wick rejection; Volume spike without continuation | 1 |
| Strong liquidity trap (0.95): Sweep of previous high; Equal lows; False resistance break; Stop hunt candidate; Long wick rejection; Volume spike without continuation | 1 |
| Sweep of previous high | 1 |

## What the data supports

A single feature (for example one long wick) is insufficient to declare a false breakout. The current detector requires multiple independent evidences; the table above shows which features differed between ideas that would have won and lost. Any future rule change must be validated as a separate, isolated experiment before touching production.

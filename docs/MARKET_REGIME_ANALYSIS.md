# Market Regime Analysis

Based on **196** filtered trades across 12 symbols (2026-06-19 → 2026-11-16).

Regime labels are computed at the decision bar using only past data: 30-day return, price vs 200-bar SMA, SMA slope, ATR percentile and 1H CHoCH presence. Buckets can overlap (trend regime + volatility regime + reversal flag).

## 1. Trend regimes

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| bear | 29 | 4 | 25 | 13.79 | 0.35 | -0.6958 | -24.6628 |
| bull | 39 | 10 | 29 | 25.64 | 0.78 | -0.1982 | -14.7440 |
| sideways | 119 | 36 | 83 | 30.25 | 0.91 | -0.0840 | -24.8386 |
| unknown | 9 | 5 | 4 | 55.56 | 2.88 | 1.0057 | -3.6726 |

## 2. Volatility regimes

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| high | 58 | 22 | 36 | 37.93 | 1.43 | 0.3166 | -14.5059 |
| low | 72 | 17 | 55 | 23.61 | 0.61 | -0.3943 | -36.4929 |
| normal | 57 | 11 | 46 | 19.30 | 0.52 | -0.4889 | -33.4758 |
| unknown | 9 | 5 | 4 | 55.56 | 2.88 | 1.0057 | -3.6726 |

## 3. Trend reversal (1H CHoCH present)

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| False | 88 | 32 | 56 | 36.36 | 1.23 | 0.1829 | -19.3966 |
| True | 108 | 23 | 85 | 21.30 | 0.58 | -0.4161 | -48.1507 |

## 4. Interpretation limits

- Regime buckets with fewer than ~30 trades are descriptive only; no conclusion about edge should be drawn.
- Volatility buckets are relative to each symbol's own ATR distribution, so they are comparable across assets.
- The reversal flag is a 1H CHoCH near entry, not a full regime-transition model.


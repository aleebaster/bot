# Multi-Asset Backtest

Generated: 2026-11-16T16:46:23.824989+00:00  
Period: **2026-06-19 → 2026-11-16** (target 150 days per symbol)  
Timeframe: **15m** | Symbols: **12** | Signal Score threshold: **80** (unchanged)

Execution: next-bar open, fees + slippage + funding, conservative same-bar SL priority. Higher timeframes are aggregated only from complete bar groups; every evaluation uses a prefix ending at the decision bar. No strategy parameters were optimised.

## 1. Per-symbol results

| Symbol | Bars | Base trades | Kept | Base WR | Kept WR | Base E[R] | Kept E[R] |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 14400 | 53 | 28 | 24.53 | 28.57 | -0.396 | -0.179 |
| ETHUSDT | 14400 | 48 | 21 | 41.67 | 52.38 | 0.278 | 0.782 |
| BNBUSDT | 14400 | 52 | 18 | 25.00 | 22.22 | -0.399 | -0.535 |
| SOLUSDT | 14400 | 37 | 17 | 29.73 | 29.41 | -0.047 | -0.040 |
| XRPUSDT | 14400 | 53 | 17 | 24.53 | 35.29 | -0.302 | 0.135 |
| DOGEUSDT | 14400 | 39 | 14 | 28.21 | 28.57 | -0.128 | -0.149 |
| ADAUSDT | 14400 | 32 | 9 | 28.12 | 0.00 | -0.076 | -1.175 |
| LINKUSDT | 14400 | 44 | 19 | 29.55 | 21.05 | -0.076 | -0.384 |
| AVAXUSDT | 14400 | 38 | 10 | 23.68 | 30.00 | -0.271 | 0.007 |
| NEARUSDT | 14400 | 19 | 5 | 21.05 | 40.00 | -0.313 | 0.454 |
| SUIUSDT | 14400 | 40 | 20 | 20.00 | 25.00 | -0.443 | -0.236 |
| LTCUSDT | 14400 | 49 | 18 | 26.53 | 16.67 | -0.201 | -0.551 |

## 2. Aggregate results (base vs filtered)

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| Base strategy | 504 | 137 | 367 | 27.18 | 0.79 | -0.1999 | -141.0193 |
| With false-signal filter | 196 | 55 | 141 | 28.06 | 0.84 | -0.1472 | -50.2468 |

Trade counts: base **504**, filtered **196**, rejected **308**.

## 3. Bootstrap 95% confidence intervals (percentile, seed 42)

| Metric | n | Mean | CI low | CI high |
|---|---|---|---|---|
| base_expectancy | 504 | -0.1999 | -0.3611 | -0.0560 |
| filtered_expectancy | 196 | -0.1472 | -0.3867 | 0.1011 |
| base_winrate | 504 | 0.2718 | 0.2321 | 0.3095 |
| filtered_winrate | 196 | 0.2806 | 0.2194 | 0.3418 |

## 4. In-sample / validation / out-of-sample (filtered trades)

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| in_sample | 116 | 33 | 83 | 28.45 | 0.84 | -0.1456 | -37.3848 |
| out_of_sample | 40 | 9 | 31 | 22.50 | 0.63 | -0.3664 | -23.4585 |
| validation | 40 | 13 | 27 | 32.50 | 1.08 | 0.0674 | -12.6224 |

## 5. Walk-forward windows (filtered trades)

| Group | Trades | Wins | Losses | Win rate % | PF | Expectancy R | Max DD R |
|---|---|---|---|---|---|---|---|
| Window 0 | 48 | 19 | 29 | 39.58 | 1.38 | 0.2932 | -9.2049 |
| Window 1 | 39 | 6 | 33 | 15.38 | 0.39 | -0.6562 | -31.0445 |
| Window 2 | 29 | 8 | 21 | 27.59 | 0.80 | -0.1852 | -11.7916 |
| Window 3 | 32 | 11 | 21 | 34.38 | 1.17 | 0.1377 | -12.6224 |
| Window 4 | 16 | 3 | 13 | 18.75 | 0.51 | -0.4837 | -12.1021 |
| Window 5 | 32 | 8 | 24 | 25.00 | 0.72 | -0.2695 | -19.9601 |

## 6. Limitations

- The base backtester is single-timeframe (15M); 5M/15M roles are approximated by the same series and higher timeframes are aggregated from it. This is a documented approximation.
- Small per-symbol trade counts make most per-symbol differences statistically weak.
- Bootstrap intervals resample trades; they do not correct for regime dependence or serial correlation.
- No parameter was tuned on this dataset; results are reported as observed, not as a forecast.


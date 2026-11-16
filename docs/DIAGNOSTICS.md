# Crypto Futures Signal Bot — Diagnostic Report

Generated: **2026-11-16 13:06 UTC**  
Collection: **189.44s** total (REST 30.75s, analysis 158.7s), **60** REST calls.  
Config: min score **80**, min RR **2.0**, quote-age **180s**, scan interval **60s**, OHLCV limit **400**, WS requested **True**.

> This report is generated from live Binance USD-M futures data by `python -m scripts.diagnose`. 
> No thresholds, weights or strategy rules were weakened to obtain these numbers.

## 1. Executive summary

The reported run (`scanned=12, signals=0, no_trade=12`) was **not** caused by market conditions alone. Two program-level defects were found and fixed before the final measurement:

1. **Flat 180s freshness limit applied to every timeframe.** A closed 1D bar is legitimately 12–48h old at its open timestamp, so all 12 symbols were rejected with `Stale data on 1d` before any strategy logic ran. Fixed with a timeframe-aware tolerance (`max(quote_age, 2 × bar duration + 60s)`); a dead 5M feed is still rejected.
2. **WebSocket never activated.** `ccxt.async_support.binance` reports `watchOHLCV=None` and its `watch_ohlcv()` raises `NotSupported`. The bot therefore used REST polling. `ccxt.pro.binance` reports and implements `watchOHLCV=True`; a live stream test succeeded, so streaming was enabled via a separate pro client with staggered subscriptions.

After these fixes, all 12 symbols still return NO TRADE — but now for **legitimate strategy reasons** (5M trigger/structure/volume/score), confirmed by an independent cross-check of 12/12 engine reasons against the diagnostic filter trace.

## 2. Per-coin indicator snapshot (closed bars only)

Prices are shown with 6 significant digits. RV = last closed volume / SMA20 of prior volumes.

### BTCUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 54.4 | 48.5 | 47.1 | 64170.1 | 64244.2 | 64366.7 | 64643.5 | 25.8 | 20.7 / 19.6 | 152.112 | 64826.9 |
| 15m | 41.1 | 42.2 | 43.2 | 64274.8 | 64403.2 | 64582.4 | 65419.4 | 20.4 | 18.3 / 26.4 | 258.767 | 67047.1 |
| 1h | 35.7 | 41.0 | 41.8 | 64504.4 | 64705.3 | 65421.9 | 69793.6 | 11.8 | 17.3 / 24.8 | 564.465 | 72728.2 |
| 4h | 32.4 | 30.0 | 29.7 | 65102.1 | 66642.3 | 69851.7 | 76081.5 | 63.6 | 6.9 / 30.0 | 1326.18 | 79346.6 |
| 1d | 19.2 | 24.2 | 28.7 | 70346.1 | 74195 | 77138.1 | 76188.6 | 31.7 | 7.5 / 40.6 | 2751.18 | 77650.3 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 64242.5 | RANGING | 0.52 | BEARISH | BEARISH | BEARISH | RANGING | 719.23 | 788.81 | 0.94 |
| 15m | 64137.1 | BEARISH | 0.41 | BEARISH | BEARISH | BEARISH | RANGING | 2871.47 | 1894.32 | 1.58 |
| 1h | 64137.1 | BEARISH | 0.24 | BEARISH | BEARISH | BEARISH | BEARISH | 12478.10 | 6029.01 | 2.16 |
| 4h | 64413.9 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 25408.38 | 40794.31 | 0.59 |
| 1d | 65309.8 | BEARISH | 0.63 | MIXED | BEARISH | BEARISH | BEARISH | 251263.27 | 163588.20 | 1.59 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: bullish
- MTF context: higher **BEARISH**, 1H **BEARISH**, bias **BEARISH**, trend score **16.61/20**, aligned LONG=False, SHORT=True

### ETHUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 59.9 | 53.2 | 51.1 | 1798.66 | 1799.87 | 1802.65 | 1810.82 | 24.3 | 22.1 / 17.2 | 5.44171 | 1813.23 |
| 15m | 46.5 | 45.2 | 45.3 | 1800.26 | 1803.62 | 1809.04 | 1832.24 | 16.0 | 16.8 / 24.3 | 9.00906 | 1873.62 |
| 1h | 38.6 | 43.3 | 43.8 | 1807.86 | 1812.69 | 1832.54 | 1974.95 | 10.3 | 18.2 / 24.6 | 19.408 | 2086.51 |
| 4h | 36.9 | 34.7 | 34.0 | 1824.57 | 1869.95 | 1977.06 | 2222.64 | 60.5 | 7.0 / 28.3 | 47.5383 | 2402.55 |
| 1d | 23.3 | 26.0 | 29.3 | 1989.68 | 2135.06 | 2277.67 | 2301.87 | 33.0 | 8.7 / 37.4 | 110.023 | 2429.28 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 1803 | RANGING | 0.49 | MIXED | BEARISH | BEARISH | RANGING | 14252.49 | 14593.45 | 1.01 |
| 15m | 1799.19 | RANGING | 0.32 | BEARISH | BEARISH | BEARISH | RANGING | 38685.44 | 43117.36 | 0.92 |
| 1h | 1799.19 | RANGING | 0.21 | BEARISH | BEARISH | BEARISH | RANGING | 224811.44 | 139957.82 | 1.59 |
| 4h | 1805.29 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 637535.70 | 958676.50 | 0.64 |
| 1d | 1834.28 | BEARISH | 0.66 | BEARISH | BEARISH | BEARISH | RANGING | 5694651.58 | 3855094.43 | 1.52 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **12.98/20**, aligned LONG=False, SHORT=True

### BNBUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 58.0 | 50.2 | 48.3 | 587.544 | 588.331 | 589.402 | 591.405 | 26.4 | 23.2 / 20.0 | 1.33286 | 592.598 |
| 15m | 40.1 | 42.0 | 43.4 | 588.591 | 589.635 | 590.903 | 598.174 | 17.9 | 11.3 / 26.4 | 2.19059 | 613.189 |
| 1h | 35.5 | 41.6 | 42.2 | 590.551 | 591.871 | 598.351 | 639.32 | 16.8 | 16.1 / 26.5 | 4.82132 | 665.203 |
| 4h | 34.9 | 31.7 | 31.6 | 595.073 | 610 | 639.897 | 694.444 | 55.9 | 8.3 / 27.3 | 12.1361 | 726.563 |
| 1d | 21.4 | 26.4 | 30.8 | 644.143 | 677.588 | 703.52 | 699.009 | 36.3 | 6.9 / 39.5 | 27.4213 | 777.666 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 588.69 | RANGING | 0.53 | MIXED | BEARISH | BEARISH | RANGING | 3391.71 | 1745.19 | 2.12 |
| 15m | 587.55 | RANGING | 0.36 | BEARISH | BEARISH | BEARISH | RANGING | 7232.28 | 4233.99 | 1.80 |
| 1h | 587.55 | BEARISH | 0.34 | BEARISH | BEARISH | BEARISH | BEARISH | 26097.83 | 16025.29 | 1.64 |
| 4h | 590.22 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 58581.90 | 131917.51 | 0.42 |
| 1d | 596.93 | RANGING | 0.73 | MIXED | BEARISH | BEARISH | RANGING | 674944.19 | 640072.05 | 1.07 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Hammer, Pin Bar, Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **BEARISH**, bias **BEARISH**, trend score **12.01/20**, aligned LONG=False, SHORT=True

### SOLUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 54.0 | 48.0 | 47.4 | 70.7773 | 70.9332 | 71.0625 | 71.3495 | 30.4 | 18.5 / 21.0 | 0.254125 | 71.4792 |
| 15m | 37.5 | 42.2 | 43.9 | 70.9781 | 71.0933 | 71.2843 | 72.532 | 16.7 | 14.7 / 25.3 | 0.424612 | 74.7489 |
| 1h | 37.2 | 42.1 | 42.5 | 71.2213 | 71.4526 | 72.5405 | 79.385 | 13.8 | 17.9 / 24.8 | 0.925309 | 84.1402 |
| 4h | 37.3 | 33.8 | 33.1 | 72.0721 | 74.4409 | 79.5087 | 92.4511 | 55.5 | 9.4 / 28.3 | 2.1357 | 102.988 |
| 1d | 18.7 | 21.1 | 25.7 | 80.203 | 87.7114 | 95.5 | 96.8541 | 44.8 | 6.2 / 39.1 | 4.94766 | 105.479 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 70.91 | BEARISH | 0.61 | BEARISH | BEARISH | BEARISH | RANGING | 125048.47 | 80557.36 | 1.64 |
| 15m | 70.67 | RANGING | 0.33 | BEARISH | BEARISH | BEARISH | RANGING | 279292.34 | 192681.73 | 1.51 |
| 1h | 70.67 | RANGING | 0.28 | BEARISH | BEARISH | BEARISH | RANGING | 1112457.92 | 745076.72 | 1.49 |
| 4h | 71.34 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 2741176.72 | 4764894.84 | 0.56 |
| 1d | 72.71 | BEARISH | 0.90 | BEARISH | BEARISH | BEARISH | BEARISH | 29622731.88 | 18042990.31 | 1.72 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Outside Bar, Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **13.69/20**, aligned LONG=False, SHORT=True

### XRPUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 58.8 | 53.1 | 51.6 | 0.949716 | 0.950589 | 0.951385 | 0.95574 | 26.5 | 23.1 / 20.5 | 0.00310169 | 0.959236 |
| 15m | 44.9 | 45.7 | 45.9 | 0.950616 | 0.951634 | 0.954404 | 0.964318 | 17.7 | 15.8 / 24.4 | 0.0052325 | 0.977474 |
| 1h | 42.0 | 44.9 | 45.3 | 0.953581 | 0.956212 | 0.964494 | 1.03632 | 9.6 | 19.3 / 24.9 | 0.0116453 | 1.10492 |
| 4h | 41.7 | 39.2 | 37.7 | 0.96255 | 0.981562 | 1.03753 | 1.19755 | 52.8 | 10.4 / 26.1 | 0.0266914 | 1.34154 |
| 1d | 27.1 | 27.0 | 30.2 | 1.04295 | 1.13864 | 1.23857 | 1.33176 | 33.3 | 8.6 / 37.9 | 0.0632804 | 1.56422 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 0.9522 | RANGING | 0.53 | MIXED | BEARISH | BEARISH | RANGING | 2524212.00 | 2398680.65 | 1.08 |
| 15m | 0.9491 | RANGING | 0.35 | BEARISH | BEARISH | BEARISH | RANGING | 6175550.30 | 7707228.80 | 0.80 |
| 1h | 0.9491 | BEARISH | 0.19 | BEARISH | BEARISH | BEARISH | BEARISH | 33862513.30 | 25517807.02 | 1.33 |
| 4h | 0.9555 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | RANGING | 120282062.70 | 156379993.84 | 0.75 |
| 1d | 0.9734 | BEARISH | 0.67 | BEARISH | BEARISH | BEARISH | RANGING | 885440857.40 | 634008311.69 | 1.45 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: hidden_bearish
- MTF context: higher **BEARISH**, 1H **BEARISH**, bias **BEARISH**, trend score **16.57/20**, aligned LONG=False, SHORT=True

### DOGEUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 57.3 | 51.1 | 49.8 | 0.0583558 | 0.0584421 | 0.05853 | 0.0587247 | 27.5 | 22.3 / 21.7 | 0.000200754 | 0.0587508 |
| 15m | 43.5 | 44.8 | 45.6 | 0.0584525 | 0.0585441 | 0.0586819 | 0.059605 | 16.6 | 15.4 / 23.7 | 0.000345147 | 0.061153 |
| 1h | 40.0 | 43.9 | 43.7 | 0.0586569 | 0.058795 | 0.0596249 | 0.0646307 | 13.8 | 16.9 / 24.0 | 0.000704347 | 0.0678755 |
| 4h | 38.3 | 35.4 | 35.0 | 0.0593021 | 0.0610822 | 0.0647151 | 0.0736544 | 57.1 | 8.6 / 27.5 | 0.00171699 | 0.0833046 |
| 1d | 24.2 | 26.6 | 30.2 | 0.0651894 | 0.0702915 | 0.0764136 | 0.087313 | 42.1 | 6.3 / 35.3 | 0.00412956 | 0.110587 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 0.0585 | RANGING | 0.55 | MIXED | BEARISH | BEARISH | BEARISH | 23664351.00 | 18333069.25 | 1.36 |
| 15m | 0.05833 | RANGING | 0.33 | BEARISH | BEARISH | BEARISH | RANGING | 55466193.00 | 44989858.40 | 1.28 |
| 1h | 0.05833 | RANGING | 0.28 | BEARISH | BEARISH | BEARISH | RANGING | 276021307.00 | 219091896.05 | 1.26 |
| 4h | 0.05875 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 623775861.00 | 1176141512.10 | 0.51 |
| 1d | 0.05985 | BEARISH | 0.84 | BEARISH | BEARISH | BEARISH | BEARISH | 7409855272.00 | 4587787270.45 | 1.70 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Hammer, Bullish Confirmation
- RSI divergences: 5m: none; 15m: bullish, hidden_bearish
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **13.53/20**, aligned LONG=False, SHORT=True

### ADAUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 50.2 | 45.7 | 45.3 | 0.151048 | 0.151425 | 0.151842 | 0.152639 | 27.0 | 16.5 / 22.6 | 0.000635499 | 0.152777 |
| 15m | 37.4 | 40.8 | 42.6 | 0.151553 | 0.15196 | 0.1525 | 0.154981 | 17.2 | 12.5 / 22.0 | 0.00106987 | 0.159592 |
| 1h | 34.8 | 41.2 | 42.1 | 0.152289 | 0.152819 | 0.154984 | 0.167062 | 12.9 | 16.6 / 23.6 | 0.00203753 | 0.174821 |
| 4h | 35.8 | 34.5 | 35.0 | 0.154267 | 0.158742 | 0.167427 | 0.192604 | 45.3 | 10.5 / 29.1 | 0.00460743 | 0.219974 |
| 1d | 26.7 | 28.5 | 32.2 | 0.168199 | 0.182388 | 0.199756 | 0.227009 | 38.5 | 7.4 / 31.4 | 0.0124993 | 0.274401 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 0.1512 | BEARISH | 0.54 | BEARISH | BEARISH | BEARISH | RANGING | 3986589.00 | 3523512.70 | 1.18 |
| 15m | 0.1508 | RANGING | 0.34 | BEARISH | BEARISH | BEARISH | RANGING | 8090760.00 | 9401059.25 | 0.88 |
| 1h | 0.1508 | RANGING | 0.26 | BEARISH | BEARISH | BEARISH | RANGING | 47811399.00 | 30523587.15 | 1.61 |
| 4h | 0.1525 | BEARISH | 0.91 | BEARISH | BEARISH | BEARISH | BEARISH | 140209786.00 | 183702002.75 | 0.74 |
| 1d | 0.1553 | BEARISH | 0.77 | BEARISH | BEARISH | BEARISH | BEARISH | 1019365738.00 | 737583659.50 | 1.42 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **12.93/20**, aligned LONG=False, SHORT=True

### LINKUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 54.5 | 49.1 | 48.4 | 9.08652 | 9.10139 | 9.11453 | 9.15107 | 24.9 | 21.8 / 18.9 | 0.0301877 | 9.17993 |
| 15m | 41.8 | 44.2 | 45.0 | 9.10513 | 9.11714 | 9.14094 | 9.25141 | 15.0 | 15.0 / 24.2 | 0.0521549 | 9.44614 |
| 1h | 39.1 | 43.3 | 43.9 | 9.13282 | 9.15869 | 9.25399 | 9.88359 | 12.3 | 18.0 / 24.7 | 0.109123 | 10.4904 |
| 4h | 38.1 | 36.4 | 36.6 | 9.21777 | 9.42897 | 9.89259 | 11.0717 | 46.1 | 11.0 / 27.6 | 0.256858 | 12.2835 |
| 1d | 29.4 | 32.6 | 36.0 | 9.9431 | 10.6222 | 11.3237 | 10.9431 | 32.3 | 7.9 / 29.2 | 0.707693 | 11.458 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 9.102 | RANGING | 0.50 | MIXED | BEARISH | BEARISH | RANGING | 37161.94 | 31271.93 | 1.23 |
| 15m | 9.081 | RANGING | 0.30 | BEARISH | BEARISH | BEARISH | RANGING | 82052.65 | 95894.96 | 0.88 |
| 1h | 9.081 | RANGING | 0.25 | BEARISH | BEARISH | BEARISH | RANGING | 441838.75 | 350670.10 | 1.26 |
| 4h | 9.149 | BEARISH | 0.92 | BEARISH | BEARISH | BEARISH | RANGING | 1476060.50 | 2490504.41 | 0.57 |
| 1d | 9.289 | RANGING | 0.65 | MIXED | BEARISH | BEARISH | RANGING | 13973118.94 | 12534859.91 | 1.14 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **7.68/20**, aligned LONG=False, SHORT=True

### AVAXUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 50.2 | 46.5 | 46.2 | 7.08289 | 7.09602 | 7.11251 | 7.15697 | 24.5 | 16.2 / 20.9 | 0.0274652 | 7.19147 |
| 15m | 40.5 | 43.0 | 44.0 | 7.09973 | 7.11633 | 7.14598 | 7.35246 | 15.5 | 14.9 / 21.6 | 0.0487331 | 7.70257 |
| 1h | 31.5 | 38.2 | 38.8 | 7.13642 | 7.17759 | 7.34808 | 7.92521 | 23.1 | 14.5 / 23.8 | 0.0975086 | 8.26511 |
| 4h | 25.8 | 29.4 | 33.1 | 7.27112 | 7.56217 | 7.93409 | 8.67507 | 40.4 | 10.1 / 32.4 | 0.231911 | 9.66192 |
| 1d | 30.1 | 33.9 | 37.2 | 7.95935 | 8.387 | 8.80471 | 8.94995 | 20.2 | 13.1 / 30.6 | 0.627877 | 10.6763 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 7.088 | BEARISH | 0.49 | BEARISH | BEARISH | BEARISH | BEARISH | 38513.00 | 37342.80 | 1.04 |
| 15m | 7.074 | RANGING | 0.31 | BEARISH | BEARISH | BEARISH | RANGING | 90664.00 | 142616.70 | 0.64 |
| 1h | 7.074 | BEARISH | 0.46 | BEARISH | BEARISH | BEARISH | RANGING | 562662.00 | 468503.95 | 1.21 |
| 4h | 7.132 | BEARISH | 0.81 | BEARISH | BEARISH | BEARISH | BEARISH | 2289672.00 | 2877470.45 | 0.78 |
| 1d | 7.304 | BEARISH | 0.40 | BEARISH | BEARISH | BEARISH | RANGING | 16555169.00 | 14399185.90 | 1.18 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **BEARISH**, bias **BEARISH**, trend score **15.83/20**, aligned LONG=False, SHORT=True

### NEARUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 42.7 | 40.6 | 41.9 | 3.14232 | 3.15808 | 3.17001 | 3.17126 | 29.4 | 21.1 / 29.8 | 0.0176731 | 3.16018 |
| 15m | 31.4 | 38.5 | 42.0 | 3.16342 | 3.1718 | 3.1727 | 3.1948 | 18.6 | 14.9 / 25.8 | 0.0289453 | 3.26721 |
| 1h | 35.6 | 43.8 | 45.0 | 3.17335 | 3.17131 | 3.19743 | 3.43311 | 12.3 | 18.7 / 22.5 | 0.0553176 | 3.70225 |
| 4h | 47.1 | 41.7 | 40.9 | 3.19307 | 3.26605 | 3.44305 | 3.99292 | 31.7 | 12.5 / 23.2 | 0.123053 | 4.36614 |
| 1d | 30.6 | 35.1 | 39.8 | 3.45123 | 3.80106 | 3.99059 | 3.01226 | 25.8 | 10.7 / 26.1 | 0.389413 | 2.46898 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 3.139 | BEARISH | 0.59 | BEARISH | BEARISH | BEARISH | RANGING | 535799.00 | 463294.30 | 1.21 |
| 15m | 3.131 | RANGING | 0.37 | BEARISH | BEARISH | BEARISH | RANGING | 1290465.00 | 865528.80 | 1.57 |
| 1h | 3.131 | RANGING | 0.25 | BEARISH | BEARISH | BEARISH | RANGING | 7059695.00 | 2714866.00 | 2.79 |
| 4h | 3.199 | BEARISH | 0.63 | BEARISH | BEARISH | BEARISH | BEARISH | 10250881.00 | 18711002.95 | 0.53 |
| 1d | 3.213 | RANGING | 0.52 | MIXED | BULLISH | BULLISH | BEARISH | 95942104.00 | 114452478.65 | 0.83 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bearish Engulfing, Inside Bar
- RSI divergences: 5m: none; 15m: none
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **6.54/20**, aligned LONG=False, SHORT=True

### SUIUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 51.6 | 45.5 | 45.0 | 0.713353 | 0.715562 | 0.717915 | 0.7219 | 28.4 | 18.2 / 25.4 | 0.00284185 | 0.723032 |
| 15m | 34.9 | 39.3 | 41.6 | 0.716018 | 0.718307 | 0.721008 | 0.732289 | 14.1 | 16.4 / 24.9 | 0.00489698 | 0.754114 |
| 1h | 33.5 | 40.6 | 42.0 | 0.719899 | 0.722517 | 0.732364 | 0.786942 | 12.5 | 18.8 / 25.8 | 0.00986352 | 0.830791 |
| 4h | 37.2 | 36.3 | 36.9 | 0.728851 | 0.749179 | 0.788304 | 0.884464 | 46.6 | 10.1 / 27.1 | 0.0230605 | 0.975343 |
| 1d | 30.3 | 33.4 | 37.2 | 0.792288 | 0.849712 | 0.901746 | 0.948877 | 32.3 | 8.4 / 29.3 | 0.0635746 | 1.15008 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 0.7145 | BEARISH | 0.57 | BEARISH | BEARISH | BEARISH | RANGING | 755747.60 | 590419.84 | 1.29 |
| 15m | 0.7118 | RANGING | 0.28 | BEARISH | BEARISH | BEARISH | RANGING | 1703862.80 | 1636155.82 | 1.08 |
| 1h | 0.7118 | RANGING | 0.25 | BEARISH | BEARISH | BEARISH | RANGING | 9137263.10 | 5816235.74 | 1.56 |
| 4h | 0.7203 | BEARISH | 0.93 | BEARISH | BEARISH | BEARISH | RANGING | 23585853.30 | 40301033.76 | 0.57 |
| 1d | 0.7371 | BEARISH | 0.65 | BEARISH | BEARISH | BEARISH | RANGING | 218191195.10 | 199753313.89 | 1.10 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Bullish Confirmation
- RSI divergences: 5m: none; 15m: bullish
- MTF context: higher **BEARISH**, 1H **RANGING**, bias **BEARISH**, trend score **12.66/20**, aligned LONG=False, SHORT=True

### LTCUSDT

**Indicators**

| TF | RSI7 | RSI14 | RSI21 | EMA9 | EMA21 | EMA50 | EMA200 | ADX | +DI / -DI | ATR14 | VWAP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5m | 57.0 | 50.3 | 48.6 | 44.2094 | 44.2756 | 44.3802 | 44.6868 | 22.6 | 22.9 / 20.7 | 0.134612 | 44.9013 |
| 15m | 41.8 | 42.3 | 42.9 | 44.2955 | 44.4108 | 44.6129 | 45.4779 | 22.8 | 14.7 / 26.1 | 0.233428 | 46.7403 |
| 1h | 36.1 | 40.0 | 40.7 | 44.5322 | 44.7792 | 45.4946 | 48.5706 | 21.1 | 13.6 / 25.9 | 0.503381 | 50.5521 |
| 4h | 29.8 | 31.7 | 33.4 | 45.2119 | 46.4524 | 48.6231 | 54.1629 | 51.5 | 8.8 / 32.0 | 1.13201 | 61.1057 |
| 1d | 24.5 | 29.1 | 33.2 | 48.9577 | 52.137 | 55.3301 | 55.7313 | 40.5 | 6.5 / 30.9 | 2.98248 | 67.1739 |

**Trend, structure and volume**

| TF | Close | Trend | Strength | EMA align | vs VWAP | vs EMA200 | Structure | Volume | VolSMA20 | RV |
|---|---:|---|---:|---|---|---|---|---:|---:|---:|
| 5m | 44.31 | RANGING | 0.45 | MIXED | BEARISH | BEARISH | RANGING | 3429.67 | 4629.91 | 0.75 |
| 15m | 44.2 | BEARISH | 0.46 | BEARISH | BEARISH | BEARISH | RANGING | 11074.94 | 14448.20 | 0.78 |
| 1h | 44.2 | BEARISH | 0.42 | BEARISH | BEARISH | BEARISH | BEARISH | 72601.15 | 45885.72 | 1.62 |
| 4h | 44.46 | BEARISH | 1.00 | BEARISH | BEARISH | BEARISH | BEARISH | 216362.89 | 298337.35 | 0.69 |
| 1d | 45.53 | BEARISH | 0.81 | BEARISH | BEARISH | BEARISH | BEARISH | 1727163.64 | 1243855.64 | 1.44 |

- Candlestick patterns (last closed bar): 5m: Bullish Confirmation; 15m: Hammer, Bullish Confirmation
- RSI divergences: 5m: none; 15m: bullish
- MTF context: higher **BEARISH**, 1H **BEARISH**, bias **BEARISH**, trend score **17.69/20**, aligned LONG=False, SHORT=True

## 3. Signal Score — LONG vs SHORT

Scores are computed by the unchanged `score_setup()` for both directions using the same indicators. A low score is a strategy verdict, not a data failure.

| Symbol | LONG score | Category | SHORT score | Category | Direction allowed by MTF |
|---|---:|---|---:|---|---|
| BTCUSDT | 44.39 | Ignore | 72.61 | Moderate | BEARISH |
| ETHUSDT | 31.99 | Ignore | 53.58 | Ignore | BEARISH |
| BNBUSDT | 48.51 | Ignore | 62.01 | Ignore | BEARISH |
| SOLUSDT | 45.68 | Ignore | 67.04 | Ignore | BEARISH |
| XRPUSDT | 35.83 | Ignore | 63.93 | Ignore | BEARISH |
| DOGEUSDT | 44.36 | Ignore | 70.71 | Moderate | BEARISH |
| ADAUSDT | 25.17 | Ignore | 58.93 | Ignore | BEARISH |
| LINKUSDT | 30.27 | Ignore | 54.68 | Ignore | BEARISH |
| AVAXUSDT | 28.53 | Ignore | 62.83 | Ignore | BEARISH |
| NEARUSDT | 26.72 | Ignore | 64.94 | Ignore | BEARISH |
| SUIUSDT | 28.43 | Ignore | 63.66 | Ignore | BEARISH |
| LTCUSDT | 37.12 | Ignore | 62.69 | Ignore | BEARISH |

### Score component detail

| Symbol | Dir | MTF/20 | RSI/15 | Candle/15 | Struct/15 | S-R/10 | Volume/10 | EMA-VWAP/10 | Vol-entry/5 | Total |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | LONG | 6.6 | 2.5 | 6.2 | 6.0 | 10.0 | 8.0 | 0.0 | 5.0 | 44.39 |
| BTCUSDT | SHORT | 16.6 | 9.0 | 0.0 | 14.0 | 10.0 | 8.0 | 10.0 | 5.0 | 72.61 |
| ETHUSDT | LONG | 5.2 | 3.0 | 6.2 | 3.0 | 9.6 | 0.0 | 0.0 | 5.0 | 31.99 |
| ETHUSDT | SHORT | 13.0 | 6.0 | 0.0 | 10.0 | 9.6 | 0.0 | 10.0 | 5.0 | 53.58 |
| BNBUSDT | LONG | 4.8 | 0.0 | 9.7 | 11.0 | 10.0 | 8.0 | 0.0 | 5.0 | 48.51 |
| BNBUSDT | SHORT | 12.0 | 9.0 | 0.0 | 8.0 | 10.0 | 8.0 | 10.0 | 5.0 | 62.01 |
| SOLUSDT | LONG | 5.5 | 0.0 | 6.2 | 11.0 | 10.0 | 8.0 | 0.0 | 5.0 | 45.68 |
| SOLUSDT | SHORT | 13.7 | 9.0 | 3.1 | 11.0 | 7.2 | 8.0 | 10.0 | 5.0 | 67.04 |
| XRPUSDT | LONG | 6.6 | 0.0 | 6.2 | 8.0 | 10.0 | 0.0 | 0.0 | 5.0 | 35.83 |
| XRPUSDT | SHORT | 16.6 | 11.4 | 0.0 | 11.0 | 10.0 | 0.0 | 10.0 | 5.0 | 63.93 |
| DOGEUSDT | LONG | 5.4 | 2.2 | 9.6 | 9.0 | 7.2 | 6.0 | 0.0 | 5.0 | 44.36 |
| DOGEUSDT | SHORT | 13.5 | 11.6 | 0.0 | 15.0 | 9.6 | 6.0 | 10.0 | 5.0 | 70.71 |
| ADAUSDT | LONG | 5.2 | 0.0 | 6.2 | 0.0 | 8.8 | 0.0 | 0.0 | 5.0 | 25.17 |
| ADAUSDT | SHORT | 12.9 | 9.0 | 0.0 | 12.0 | 10.0 | 0.0 | 10.0 | 5.0 | 58.93 |
| LINKUSDT | LONG | 3.1 | 0.0 | 6.2 | 6.0 | 10.0 | 0.0 | 0.0 | 5.0 | 30.27 |
| LINKUSDT | SHORT | 7.7 | 9.0 | 0.0 | 15.0 | 8.0 | 0.0 | 10.0 | 5.0 | 54.68 |
| AVAXUSDT | LONG | 6.3 | 0.0 | 6.2 | 3.0 | 8.0 | 0.0 | 0.0 | 5.0 | 28.53 |
| AVAXUSDT | SHORT | 15.8 | 9.0 | 0.0 | 15.0 | 8.0 | 0.0 | 10.0 | 5.0 | 62.83 |
| NEARUSDT | LONG | 2.6 | 0.0 | 3.1 | 0.0 | 8.0 | 8.0 | 0.0 | 5.0 | 26.72 |
| NEARUSDT | SHORT | 6.5 | 9.0 | 5.6 | 12.0 | 8.8 | 8.0 | 10.0 | 5.0 | 64.94 |
| SUIUSDT | LONG | 5.1 | 3.0 | 6.2 | 0.0 | 7.2 | 2.0 | 0.0 | 5.0 | 28.43 |
| SUIUSDT | SHORT | 12.7 | 9.0 | 0.0 | 15.0 | 10.0 | 2.0 | 10.0 | 5.0 | 63.66 |
| LTCUSDT | LONG | 7.1 | 2.3 | 9.6 | 6.0 | 7.2 | 0.0 | 0.0 | 5.0 | 37.12 |
| LTCUSDT | SHORT | 17.7 | 9.0 | 0.0 | 11.0 | 10.0 | 0.0 | 10.0 | 5.0 | 62.69 |

## 4. Exact rejection reasons and hard filters

| Symbol | Engine reason | First failed filter | ALL failed hard filters |
|---|---|---|---|
| BTCUSDT | No 5M candlestick trigger | trigger_candle_5m | **trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**volume**: RV(5m)=0.94, RV(15m)=1.58<br>**score_threshold**: score=72.61 vs threshold 80 |
| ETHUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=1803.00000000, EMA21=1799.87051089, VWAP=1813.23464605<br>**trigger_rsi_5m**: RSI14(5m)=53.22, cross50=(True,False)<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=53.58 vs threshold 80 |
| BNBUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=588.69000000, EMA21=588.33111416, VWAP=592.59812711<br>**trigger_rsi_5m**: RSI14(5m)=50.22, cross50=(True,False)<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=62.01 vs threshold 80 |
| SOLUSDT | 15M market structure does not confirm setup | setup_structure_15m | **setup_structure_15m**: structure=RANGING, events=['BOS:BULLISH', 'CHoCH:BULLISH', 'CHoCH:BULLISH'], sweep=Sweep(direction='BULLISH', level=70.57, confirmed=False)<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=67.04 vs threshold 80<br>**false_breakout**: false_breakout=True |
| XRPUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=0.95220000, EMA21=0.95058896, VWAP=0.95923570<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=63.93 vs threshold 80<br>**false_breakout**: false_breakout=True |
| DOGEUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=0.05850000, EMA21=0.05844206, VWAP=0.05875076<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=70.71 vs threshold 80<br>**false_breakout**: false_breakout=True |
| ADAUSDT | No 5M candlestick trigger | trigger_candle_5m | **trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=58.93 vs threshold 80 |
| LINKUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=9.10200000, EMA21=9.10139337, VWAP=9.17992526<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=54.68 vs threshold 80 |
| AVAXUSDT | No 5M candlestick trigger | trigger_candle_5m | **trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**volume**: RV(5m)=1.04, RV(15m)=0.64<br>**score_threshold**: score=62.83 vs threshold 80 |
| NEARUSDT | No 5M candlestick trigger | trigger_candle_5m | **trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=64.94 vs threshold 80 |
| SUIUSDT | No 5M candlestick trigger | trigger_candle_5m | **trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**score_threshold**: score=63.66 vs threshold 80 |
| LTCUSDT | 5M EMA/VWAP trigger not met | trigger_ema_vwap_5m | **trigger_ema_vwap_5m**: close=44.31000000, EMA21=44.27562593, VWAP=44.90134459<br>**trigger_rsi_5m**: RSI14(5m)=50.34, cross50=(True,False)<br>**trigger_candle_5m**: patterns=['Bullish Confirmation:BULLISH']<br>**volume**: RV(5m)=0.75, RV(15m)=0.78<br>**score_threshold**: score=62.69 vs threshold 80<br>**false_breakout**: false_breakout=True |

### Trade-plan diagnostics for both directions

| Symbol | LONG plan | SHORT plan |
|---|---|---|
| BTCUSDT | OK: SL=64035.48654036, RR=1:3.89, stop=0.80x ATR, size=0.015566, cost=1.7000 | OK: SL=64449.51345964, RR=1:4.64, stop=0.80x ATR, size=0.015566, cost=1.7000 |
| ETHUSDT | OK: SL=1789.71582868, RR=1:4.11, stop=1.47x ATR, size=0.376388, cost=1.1537 | OK: SL=1811.00417132, RR=1:3.87, stop=0.89x ATR, size=0.554631, cost=1.7000 |
| BNBUSDT | OK: SL=586.93752580, RR=1:3.57, stop=0.80x ATR, size=1.698687, cost=1.7000 | OK: SL=591.63328593, RR=1:5.51, stop=1.34x ATR, size=1.698687, cost=1.7000 |
| SOLUSDT | OK: SL=70.57031079, RR=1:3.03, stop=0.80x ATR, size=14.102383, cost=1.7000 | OK: SL=71.24968921, RR=1:4.27, stop=0.80x ATR, size=14.102383, cost=1.7000 |
| XRPUSDT | OK: SL=0.94801400, RR=1:3.65, stop=0.80x ATR, size=1050.199538, cost=1.7000 | OK: SL=0.95771017, RR=1:9.73, stop=1.05x ATR, size=907.413163, cost=1.4689 |
| DOGEUSDT | OK: SL=0.05822388, RR=1:3.69, stop=0.80x ATR, size=17094.017094, cost=1.7000 | OK: SL=0.05880008, RR=1:3.03, stop=0.87x ATR, size=16662.481445, cost=1.6571 |
| ADAUSDT | OK: SL=0.15034410, RR=1:3.13, stop=0.80x ATR, size=5841.815915, cost=1.5016 | OK: SL=0.15205590, RR=1:3.27, stop=0.80x ATR, size=5841.815915, cost=1.5016 |
| LINKUSDT | OK: SL=9.05998123, RR=1:3.89, stop=0.81x ATR, size=109.865964, cost=1.7000 | OK: SL=9.14372389, RR=1:11.45, stop=0.80x ATR, size=109.865964, cost=1.7000 |
| AVAXUSDT | OK: SL=7.04901355, RR=1:4.18, stop=0.80x ATR, size=128.249691, cost=1.5454 | OK: SL=7.12698645, RR=1:4.16, stop=0.80x ATR, size=128.249691, cost=1.5454 |
| NEARUSDT | OK: SL=3.11323269, RR=1:3.34, stop=0.89x ATR, size=194.044333, cost=1.0355 | OK: SL=3.16276731, RR=1:3.05, stop=0.82x ATR, size=210.373009, cost=1.1226 |
| SUIUSDT | OK: SL=0.71058242, RR=1:3.07, stop=0.80x ATR, size=1276.297745, cost=1.5503 | OK: SL=0.71841758, RR=1:8.81, stop=0.80x ATR, size=1276.297745, cost=1.5503 |
| LTCUSDT | OK: SL=44.10653879, RR=1:3.71, stop=0.87x ATR, size=22.568269, cost=1.7000 | OK: SL=44.68346121, RR=1:4.50, stop=1.60x ATR, size=13.388271, cost=1.0085 |

Cross-check: engine reason matches a failed filter in **12/12** cases — no signal was rejected by an unexplained code path.

## 5. Correctness verification

Verified with the automated suite (`python -m pytest -q`):

- RSI(14) reproduces the classic Wilder reference **70.46** on the standard 15-close series; bounds 0–100 and warm-up NaNs are asserted.
- EMA matches pandas `ewm(adjust=False)` exactly; ATR/ADX use Wilder smoothing with correct DI direction; VWAP is volume-weighted with typical price.
- Divergence classification tested on controlled pivot series (regular bullish, no-divergence flat series, 50-cross and exit flags).
- Candlestick patterns tested on explicit candle shapes (engulfing, hammer, shooting star, doji, inside/outside, three soldiers).
- Price action tests cover swing detection, same-kind HH/HL labels, bullish/bearish structure, BOS and liquidity sweeps.
- Multi-timeframe aggregation, scoring weights, trade planning, RR/sizing, chronological SL/TP, Telegram formatting and backtest splits are covered.
- New regression tests: closed 1D bar is not stale; genuinely flat 5M bar is still stale; WebSocket capability requires ccxt.pro.

Result: **79 tests passed** after the fixes (see commit history).

## 6. WebSocket investigation

| Check | Result |
|---|---|
| `ws_enabled` setting | true |
| REST client `has['watchOHLCV']` | None |
| REST client has `watch_ohlcv` attribute | True |
| REST client call result | `NotSupported: binance watchOHLCV() is not supported yet` |
| `ccxt.pro` `has['watchOHLCV']` | True |
| Live `ccxt.pro.watch_ohlcv('BTC/USDT:USDT','15m')` | succeeded, returned a closed-bar snapshot |
| Feed capability after fix | True |

Conclusion: WebSocket was disabled because the capability probe looked at the **REST** ccxt client, where streaming is intentionally unsupported. It is safe to activate via `ccxt.pro`: the pro client is public-data only, uses the same symbol format, and subscriptions are now staggered by 0.3s to respect Binance's connection-open rate. REST remains for initial backfill and gap refill; on stream failure the feed reconnects with exponential backoff and refills gaps.

## 7. REST polling frequency and rate limits

- Watchlist: **12** symbols × 5 timeframes = **60** klines requests per full refresh.
- Measured REST time for the full refresh: **30.75s** (~0.51s/request including ccxt throttling and network).
- Estimated weight per refresh: **120** (400-limit klines ≈ 2 weight each).
- Nominal weight at the 60s interval: **120.0 weight/min**, vs Binance USD-M **2400 weight/min**.
- The old polling loop slept *after* the fetches, so the true period was fetch time + interval (~205s). It now sleeps only the remaining time, keeping the cadence at 60s; with WS active the poll loop is replaced by streams.
- Analysis time dominates the diagnostic run (**158.7s** for 12 symbols): repeated price-action/indicator recomputation per symbol. This affects scan latency, not correctness, and is a separate performance item.

## 8. Is NO TRADE caused by bugs or missing data?

**Before the fixes: yes** — the flat freshness threshold blocked every symbol on 1D data. 
**After the fixes: no.** Evidence:

- All required timeframes have 399 closed bars (400 fetched, forming bar excluded; minimums 40–60) — no missing history.
- All last bars are closed; forming candles are excluded by `CandleStore.get_closed()`.
- Freshness is now bar-duration aware; no symbol is rejected for stale data.
- Rejections are specific, diverse strategy conditions (5M EMA/VWAP, 5M pattern, 15M structure, volume, score).
- Every SHORT score is below the unchanged 80 threshold; several LONG scores are far below. Even if a trigger passed, the score filter would still reject them.
- The engine's first-failure reason matched the independent diagnostic trace for 12/12 symbols.

No trade was invented and the 80/100 threshold was not lowered. When conditions satisfy the strategy, the engine will emit a signal; until then NO TRADE is the correct output.


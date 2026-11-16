# Performance Report — Crypto Futures Signal Bot

Generated from real measurements on the same repo/commit lineage. All numbers below were
observed, not estimated. Thresholds and trading rules were **not** changed for performance.

## 1. Baseline (before optimisation)

Source: the live diagnostic run recorded in `docs/DIAGNOSTICS.md`.

| Metric | Before |
|---|---:|
| Symbols scanned | 12 |
| Timeframes per symbol | 5 |
| Total diagnostic run | **189.44 s** |
| REST fetch time | **30.75 s** |
| Analysis time | **158.70 s** |
| REST calls | 60 |
| WebSocket | active only after the previous fix; analysis was the bottleneck |

### cProfile of one symbol (`BTCUSDT`, diagnose + engine)

35,233,243 function calls in **42.95 s** under the profiler:

| Hotspot | Calls | Cumulative time | Root cause |
|---|---:|---:|---|
| `IndicatorSet.from_frame` | 51 | 33.23 s | Recomputed for every caller, not per frame |
| `analyze_trend` | 40 | 31.22 s | Called 5× per timeframe in the collector, each recomputing indicators + price action |
| pandas `Series.__setitem__` | 167,582 | 23.56 s | Per-bar `.iloc[i] = ...` inside Wilder/RSI loops |
| `_wilder` | 255 | 18.38 s | Same Python/pandas loop, 3 RSI + ATR + 6 ADX smoothings per frame |
| `rsi` | 182 | 16.11 s | Scalar pandas assignment per bar |
| `adx` | 51 | 15.38 s | Repeated per frame |
| `frame_to_candles` | 56 | 6.26 s | `DataFrame.iterrows()` on every call |

Conclusion: the bottleneck was **repeated computation plus pandas scalar assignment**,
not the network. REST accounted for ~16% of the run.

## 2. Changes implemented

1. **Vectorised Wilder recursion and RSI.** Loops now operate on NumPy scalars and write into a
   preallocated `np.ndarray`, removing 167k pandas setitem operations. The formula (SMA seed,
   recursive smoothing) is unchanged — the 70.46 reference still matches.
2. **Identity-guarded caches** for `IndicatorSet.from_frame`, `frame_to_candles`,
   `analyze_price_action` and `analyze_trend`. Keys include frame/list identity, length and last
   bar fingerprint, so a mutated frame cannot silently reuse stale results. Bounded to 128–256
   entries with clear-on-overflow.
3. **Removed redundant analysis calls.** The diagnostic collector now calls `analyze_trend` once
   per timeframe instead of five times.
4. **`itertuples` instead of `iterrows`** in `frame_to_candles`.
5. **Bounded parallelism** (`MAX_CONCURRENT_SYMBOLS=4`):
   - REST backfill and REST polling use `asyncio.Semaphore` + `gather`;
   - per-symbol analysis uses `asyncio.to_thread` + semaphore so the event loop stays responsive;
   - the diagnostic collector uses the same pattern.
6. **Centralised timeframe-aware freshness** in `freshness_limit_seconds()` so engine, collector
   and `/status` cannot drift apart.
7. **Candle-close scanning** (see below) replaced scanning on every fixed timer tick only.

## 3. After optimisation — measured result

Same 12 symbols, same 5 timeframes, same live Binance data:

| Metric | Before | After | Improvement |
|---|---:|---:|---:|
| Total diagnostic run | 189.44 s | **12.32 s** | **15.4×** |
| REST fetch | 30.75 s | 7.60 s | 4.0× |
| Analysis | 158.70 s | **4.70 s** | **33.8×** |
| Single symbol diagnose+engine (wall) | ~13.2 s (derived from 158.7/12) | **0.287 s** | ~46× |
| Unit/integration tests | 79 passed | **85 passed** | +6 regression tests |

Example output of the final run:

```
Collected in 12.32s | REST 7.6s | analysis 4.7s | calls 60 | WS True
Cross-check OK: 12/12
```

## 4. Rate-limit safety

- One full refresh = 12 symbols × 5 timeframes = **60 klines requests**.
- A 400-limit klines request carries weight ≈ 2 → **≈120 weight per full refresh**.
- With `SCAN_INTERVAL_SECONDS=60` that is **≈120 weight/min**, far below Binance USD-M's
  **2400 weight/min**.
- At most 4 requests are in flight simultaneously (`MAX_CONCURRENT_SYMBOLS`), and ccxt's
  per-exchange throttler remains active — concurrency does not bypass the official limiter.
- REST is now used for initial backfill and gap refill; with WebSocket active the polling loop is
  replaced by 60 multiplexed streams (12 × 5), started 0.3 s apart to respect connection-open rate.

## 5. Continuous scanning verification

A live 16-second run of `ScanScheduler.run()` with the 12-symbol watchlist produced:

```
feed_healthy True | last_scan 2026-11-16 15:53:16 | ws_capable True | WS tasks 60
```

Implemented controls:

- WebSocket via `ccxt.pro` with exponential-backoff reconnection and REST gap refill
  (regression-tested with a simulated disconnect).
- Freshness validation per timeframe using the central helper.
- A scan is triggered when a **new closed 5M bar** appears (5 s poll), on manual `/scan`, or on
  the 60 s interval — never on every price tick.
- `_scan_lock` prevents overlapping scans; `MAX_CONCURRENT_SYMBOLS` bounds CPU/REST load.
- Duplicate protection: deterministic `signal_id` + database unique key + notifier dedup + a
  per-symbol 240-minute cooldown.
- Telegram messages are emitted only for a generated signal or a lifecycle event, not per tick.

## 6. Correctness after optimisation

- `validate_strategy.py` checks cached vs uncached indicators: max absolute difference **0.000e+00**.
- No-look-ahead check on all 5 timeframes: max |full-prefix| at bar i = **0.000e+00**.
- RSI reference: **70.4641** (expected 70.46).
- All 85 tests pass, including new regression tests for caching, causality, candle-close triggers,
  cooldown, and WebSocket reconnection.

## 7. Reproduce

```bash
python -m scripts.diagnose                 # writes data/diagnostics.json
python -m scripts.build_diagnostics_report # regenerates docs/DIAGNOSTICS.md
python -m scripts.validate_strategy        # writes data/strategy_validation.json
python -m scripts.validate_paper_trading   # writes data/paper_validation.json
python -m pytest -q
```

`data/*.json` and `data/signals.db` are git-ignored runtime artefacts.

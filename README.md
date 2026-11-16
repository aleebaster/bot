# CRYPTO FUTURES SIGNAL BOT

An independent, modular crypto futures **analytics and signal generator** for Binance USD-M Futures.
It scans the market, analyses closed candles across five timeframes, and sends high-quality,
fully justified LONG/SHORT ideas to Telegram. **No real orders are ever placed.**

> Quality over quantity. If the market does not satisfy the strategy, the bot returns **NO TRADE**.
>
> **Signal-only by default:** the bot analyses Binance USDT-M Futures 24/7 and sends Telegram
> signals. It never creates, modifies or closes exchange orders. See `docs/SIGNAL_ONLY_MODE.md`.

### Validation status (read first)

A 150-day, 12-symbol validation found the base strategy had **negative expectancy (−0.1999 R)**;
the false-signal filter reduced drawdown (−141 R → −50 R) and removed 226 losing vs 82 profitable
trades, but filtered expectancy remained **−0.1472 R** (95% CI −0.3867 … +0.1011). No parameter
or threshold was tuned on this sample. Signals are analytical hypotheses, not proven edges.
Reports: `docs/MULTI_ASSET_BACKTEST.md`, `docs/MARKET_REGIME_ANALYSIS.md`,
`docs/SIGNAL_QUALITY_REPORT.md`.

---

## Features

- **Market data**: ccxt async REST + WebSocket, time synchronisation, exponential-backoff retries,
  rate limiting, gap detection, REST refill, duplicate protection, stale-quote detection,
  closed-candle-only confirmation, 24h-quote-volume auto scanner.
- **Indicators**: EMA 9/21/50/200, VWAP, ATR 14, ADX 14 (+DI/-DI), volume SMA 20,
  RSI 7/14/21 (Wilder), RSI 50-cross, momentum and 4 divergence types.
- **Price Action**: swing highs/lows, HH/HL/LH/LL, BOS, CHoCH, historical support/resistance,
  breakout, retest, false breakout, liquidity sweeps.
- **Candlesticks**: engulfing, hammer, shooting star, pin bar, morning/evening star, doji,
  inside/outside bar, three soldiers/crows, strong rejection — all with context filters.
- **Multi-timeframe engine**: 1D context → 4H trend → 1H confirmation → 15M setup → 5M trigger.
- **Signal scoring**: transparent 0–100 breakdown (weights in `docs/STRATEGY.md`), threshold 80,
  hard filters override score.
- **Risk management**: balance, risk/trade, leverage, max concurrent ideas, min RR, fee/slippage/
  funding model, ATR-plausible stops, margin cap.
- **Persistence**: SQLite + SQLAlchemy, signal dedup, chronological SL/TP resolution, MFE/MAE,
  fee-adjusted R, honest performance statistics.
- **Paper trading** (default): simulated fills, TP/SL tracking, PnL, daily reports.
- **Backtesting**: walk-forward in-sample / validation / out-of-sample, next-bar-open execution,
  conservative same-bar SL priority, costs included, no parameter optimisation.
- **Telegram**: aiogram 3.x, all required commands, admin gating, duplicate suppression.

---

## Architecture

```
app/
  main.py                 CLI entry point (scan | once | backtest | stats)
  config.py               Pydantic settings from .env
  constants.py            timeframes, watchlist, score thresholds
  market_data/            models, CandleStore, ExchangeClient, WebSocket feed
  indicators/             Wilder/EMA formulas, divergence engine
  candle_patterns/        candlestick recognition with context
  price_action/           swings, BOS/CHoCH, levels, sweeps
  trend_analysis/         trend strength + multi-timeframe aggregation
  signal_engine/          models, scoring, orchestration, hard filters
  risk_management/        trade planning, position sizing, cost model
  database/               ORM, repositories, signal tracking, statistics
  backtesting/            event-driven engine, metrics, walk-forward splits
  paper_trading/          simulated positions and daily reports
  telegram_bot/           formatting, notifier, aiogram commands
  scheduler/              periodic scanning and dispatch
tests/unit/               mathematical and logic tests
tests/integration/        database, paper trading and end-to-end flows
docs/STRATEGY.md          trading rules, scoring and risk methodology
```

Data flow:

```
Exchange (REST/WS) → CandleStore (dedup, gaps, closed bars)
   → Indicators + RSI + Patterns + Price Action
   → Multi-timeframe context → Signal Engine (filters + score)
   → Risk Manager (SL/TP/RR/size) → Database + Paper Trading → Telegram
```

---

## Installation

Requires **Python 3.12+** and Git.

### Windows

```powershell
git clone https://github.com/aleebaster/bot.git
cd bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Run:

```powershell
python -m app.main --mode scan
```

### Linux / macOS

```bash
git clone https://github.com/aleebaster/bot.git
cd bot
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
nano .env
python -m app.main --mode scan
```

### Docker

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f bot
```

### VPS

1. Create a small VPS (2 vCPU / 2 GB RAM is enough).
2. Install Docker + Docker Compose, clone the repo, fill `.env`.
3. `docker compose up -d --build`.
4. Use `systemctl` or a cron `@reboot docker compose -f /path/bot/docker-compose.yml up -d`
   for auto-start. Monitor with `docker compose logs -f bot`.

---

## Binance setup

**Public market data does not require an API key.** Leave `BINANCE_API_KEY` and
`BINANCE_API_SECRET` empty. The bot never calls trading endpoints and never requests
withdrawal permissions.

If you still want to provide keys for higher rate limits:

1. Binance → API Management → create an API key.
2. **Enable Read Only / "Enable Reading" only. NEVER enable Trading or Withdrawals.**
3. Bind the key to your VPS IP if possible.
4. Put the values in `.env` only. `.env` is git-ignored.

---

## Telegram bot setup

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the prompts.
2. Copy the token into `TELEGRAM_BOT_TOKEN`.
3. Get your numeric user ID (e.g. via **@userinfobot**) and set `TELEGRAM_CHAT_ID`.
4. For admin commands, set `ADMIN_TELEGRAM_IDS=123456789,987654321` (your user ID(s)).
5. Start the bot and send `/start`.

---

## `.env` configuration

See `.env.example` for every key. Most important:

| Key | Meaning | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather token | empty |
| `TELEGRAM_CHAT_ID` | destination chat | empty |
| `ADMIN_TELEGRAM_IDS` | comma-separated admin user IDs | empty |
| `ACCOUNT_BALANCE` | simulated balance in USDT | 1000 |
| `RISK_PER_TRADE` | risk per idea (0.005 = 0.5%) | 0.005 |
| `LEVERAGE` | margin calculation only | 1 |
| `MIN_RISK_REWARD` | minimum RR | 2.0 |
| `MIN_SIGNAL_SCORE` | send threshold | 80 |
| `MIN_VOLUME_USDT` | liquidity filter for auto scanner | 5000000 |
| `WATCHLIST` | comma-separated symbols (empty = built-in list) | empty |
| `PAPER_TRADING` | simulate positions | true |
| `DRY_RUN` | no real orders under any mode | true |

Never commit `.env`, API secrets, wallet keys or tokens.

---

## Commands

`/start`, `/help`, `/status`, `/scan`, `/signals`, `/top`, `/btc`, `/eth`, `/coin SYMBOL`,
`/stats`, `/performance`, `/watchlist`, `/settings`, `/pause`, `/resume`.

Admin-only: `/pause`, `/resume`, `/watchlist ADD|REMOVE SYMBOL`.
`/scan` is read-only and available to all users.

---

## Paper trading

Paper trading is the default and only execution mode. `PaperTradingEngine` records simulated
positions, tracks TP1/TP2/TP3 and SL, computes fee-adjusted PnL, and writes a daily report to
the database. **There is no code path that opens a real exchange order.**

Daily report: `python -m app.main --mode stats`.

---

## Testing

```bash
python -m pytest -q
```

Tests cover RSI (including the classic 70.46 Wilder reference), EMA, ATR, ADX, VWAP, divergences,
candlestick patterns, BOS/CHoCH, risk/RR/sizing, scoring, SL/TP sequencing, duplicate prevention,
Telegram formatting, signal tracking and backtesting. No real API keys are used.

---

## Backtesting

```bash
python -m app.main --mode backtest --symbol BTCUSDT --days 60
python scripts/run_backtest.py --symbol ETHUSDT --days 90
```

The report is split into in-sample (50%), validation (25%) and out-of-sample (25%). Results are
reported honestly — zero trades are shown as zero, not filled with invented statistics. See
`docs/STRATEGY.md` for the execution assumptions.

---

## GitHub workflow

```bash
git status
git add <files>
git commit -m "feat: descriptive message"
git push origin main
```

If a push is rejected because the remote moved ahead:

```bash
git pull --rebase origin main
git push origin main
```

Never force-push, never rewrite history, never change the remote.

---

## Disclaimer

This software provides analytical signals only. It is not financial advice. Cryptocurrency futures
are high risk. Backtested or paper-traded results do not guarantee future performance.

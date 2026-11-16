"""Application entry point.

Modes:
  scan     - live analytics + Telegram + paper trading (default)
  once     - single scan cycle then exit
  backtest - historical backtest from public exchange data
  stats    - print stored performance statistics
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.backtesting.engine import Backtester
from app.config import Settings, get_settings
from app.database.manager import DatabaseManager
from app.database.repository import SignalRepository
from app.database.statistics import compute_statistics
from app.logging_utils import setup_logging
from app.market_data.exchange import ExchangeClient
from app.market_data.feed import MarketDataFeed
from app.market_data.models import candles_to_frame
from app.market_data.store import CandleStore
from app.paper_trading.engine import PaperTradingEngine
from app.risk_management.manager import RiskManager
from app.scheduler.scheduler import ScanScheduler
from app.signal_engine.engine import SignalEngine
from app.telegram_bot.bot import BotContext, run_bot
from app.telegram_bot.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def build_services(settings: Settings) -> tuple[ScanScheduler, PaperTradingEngine, SignalRepository, DatabaseManager, ExchangeClient, TelegramNotifier]:
    db = DatabaseManager(settings.database_url)
    exchange = ExchangeClient(settings)
    store = CandleStore()
    feed = MarketDataFeed(exchange, store, settings)
    risk = RiskManager(settings)
    engine = SignalEngine(settings, risk)
    notifier = TelegramNotifier(settings)
    paper = PaperTradingEngine(settings, db, notifier)
    scheduler = ScanScheduler(settings, exchange, feed, store, engine, paper, notifier)
    return scheduler, paper, SignalRepository(db), db, exchange, notifier


def make_bot_context(settings: Settings, scheduler: ScanScheduler, paper: PaperTradingEngine, notifier: TelegramNotifier) -> BotContext:
    async def stats_provider() -> dict:
        return compute_statistics(await paper.signals.all_records())

    async def recent() -> list[dict]:
        records = await paper.signals.list_recent(10)
        return [
            {
                "symbol": r.symbol,
                "direction": r.direction,
                "score": r.score,
                "status": r.status,
            }
            for r in records
        ]

    return BotContext(
        settings=settings,
        notifier=notifier,
        get_status=lambda: scheduler.status(),
        request_scan=scheduler.request_scan,
        analyze_symbol=lambda symbol: scheduler.analyze_symbol(symbol.upper()),
        recent_signals=recent,
        get_stats=stats_provider,
        get_top_symbols=lambda: list(scheduler.watchlist),
        set_watchlist=scheduler.set_watchlist,
    )


async def live(settings: Settings, once: bool = False) -> None:
    scheduler, paper, signals, db, exchange, notifier = build_services(settings)
    await db.init()
    await exchange.connect()
    try:
        if once:
            await scheduler.feed.backfill(scheduler.watchlist, ["4h", "1h", "15m", "5m"])
            summary = await scheduler.scan_once()
            logger.info("Single scan summary: %s", summary)
            return
        context = make_bot_context(settings, scheduler, paper, notifier)
        scheduler.settings.paper_trading = settings.paper_trading
        await asyncio.gather(
            scheduler.run(),
            run_bot(settings, notifier, context),
        )
    finally:
        await scheduler.stop()
        await exchange.close()
        await db.close()


async def backtest(settings: Settings, symbol: str, days: int) -> None:
    exchange = ExchangeClient(settings)
    await exchange.connect()
    try:
        frame = await exchange.fetch_ohlcv(symbol, "15m", limit=min(days * 96, 1000))
        candles_frame = candles_to_frame(frame)
        result = Backtester(settings).run(candles_frame, symbol=symbol, timeframe="15m")
        print(result.as_report())
    finally:
        await exchange.close()


async def stats(settings: Settings) -> None:
    db = DatabaseManager(settings.database_url)
    await db.init()
    try:
        report = compute_statistics(await SignalRepository(db).all_records())
        for key, value in report.items():
            print(f"{key}: {value}")
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="CRYPTO FUTURES SIGNAL BOT")
    parser.add_argument("--mode", choices=["scan", "once", "backtest", "stats"], default="scan")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    try:
        if args.mode == "backtest":
            asyncio.run(backtest(settings, args.symbol.upper(), args.days))
        elif args.mode == "stats":
            asyncio.run(stats(settings))
        else:
            asyncio.run(live(settings, once=(args.mode == "once")))
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")


if __name__ == "__main__":
    main()

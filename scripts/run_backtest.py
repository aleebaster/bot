"""Convenience entry point for running a backtest from the CLI.

Example:
    python scripts/run_backtest.py --symbol BTCUSDT --days 60
"""

from __future__ import annotations

import argparse
import asyncio

from app.backtesting.engine import Backtester
from app.config import get_settings
from app.logging_utils import setup_logging
from app.market_data.exchange import ExchangeClient


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run strategy backtest")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()
    exchange = ExchangeClient(settings)
    await exchange.connect()
    try:
        frame = await exchange.fetch_ohlcv(args.symbol, "1h", limit=args.days * 24)
        result = Backtester(settings).run(frame, symbol=args.symbol)
        print(result.as_report())
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(_main())

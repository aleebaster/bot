"""Collect a read-only diagnostic snapshot of the live signal engine.

Example:
    python scripts/diagnose.py

Writes data/diagnostics.json and prints a short summary. Does not place orders,
does not persist signals and does not change any strategy threshold.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path

from app.config import get_settings
from app.constants import TIMEFRAMES
from app.diagnostics.collector import diagnose_symbol
from app.logging_utils import setup_logging
from app.market_data.exchange import ExchangeClient
from app.market_data.store import CandleStore
from app.risk_management.manager import RiskManager


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, log_to_file=False)
    exchange = ExchangeClient(settings)
    await exchange.connect()
    started = time.time()
    try:
        # Mirror production exactly: candles go through CandleStore and only
        # closed bars reach the engine.
        store = CandleStore()
        frames_by_symbol: dict[str, dict] = {}
        api_calls = 0
        fetch_started = time.time()
        for symbol in settings.watchlist:
            frames_by_symbol[symbol] = {}
            for timeframe in TIMEFRAMES:
                candles = await exchange.fetch_ohlcv(symbol, timeframe, limit=settings.ohlcv_limit)
                store.upsert_many(symbol, timeframe, candles)
                frames_by_symbol[symbol][timeframe] = store.frame(symbol, timeframe)
                api_calls += 1
        fetch_seconds = time.time() - fetch_started

        now_ms = exchange.now_ms
        risk = RiskManager(settings)
        analysis_started = time.time()
        diagnoses = [
            diagnose_symbol(symbol, frames_by_symbol[symbol], settings, risk, now_ms)
            for symbol in settings.watchlist
        ]
        analysis_seconds = time.time() - analysis_started

        has = exchange.exchange.has if exchange.exchange else {}
        report = {
            "generated_at_ms": now_ms,
            "collection_seconds": round(time.time() - started, 2),
            "fetch_seconds": round(fetch_seconds, 2),
            "analysis_seconds": round(analysis_seconds, 2),
            "settings": {
                "min_signal_score": settings.min_signal_score,
                "min_risk_reward": settings.min_risk_reward,
                "max_quote_age_seconds": settings.max_quote_age_seconds,
                "scan_interval_seconds": settings.scan_interval_seconds,
                "ws_enabled": settings.ws_enabled,
                "ohlcv_limit": settings.ohlcv_limit,
                "watchlist": settings.watchlist,
            },
            "exchange": {
                "id": settings.exchange_id,
                "futures": settings.futures,
                "ccxt_rest_watchOHLCV": has.get("watchOHLCV"),
                "ccxt_rest_watch_ohlcv_method": bool(exchange.exchange and hasattr(exchange.exchange, "watch_ohlcv")),
                "ws_capable_now": exchange.ws_capable,
                "pro_watchOHLCV": bool(exchange.pro_exchange and exchange.pro_exchange.has.get("watchOHLCV")),
                "fetch_ohlcv_weight_estimate": 2,
                "rest_calls_per_poll": api_calls,
                "estimated_weight_per_poll": api_calls * 2,
                "estimated_weight_per_minute": round(api_calls * 2 / max(settings.scan_interval_seconds, 1) * 60, 1),
                "binance_futures_weight_limit_per_minute": 2400,
            },
            "symbols": [asdict(d) for d in diagnoses],
        }

        Path("data").mkdir(exist_ok=True)
        Path("data/diagnostics.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

        print(
            f"Collected in {report['collection_seconds']}s | REST {fetch_seconds:.1f}s "
            f"| analysis {analysis_seconds:.1f}s | calls {api_calls} | WS {exchange.ws_capable}"
        )
        print(f"{'SYMBOL':<10} {'BIAS':<8} {'LONG':>7} {'SHORT':>7} {'FIRST FAILED FILTER':<28} ENGINE REASON")
        for d in diagnoses:
            failed = d.first_failed.name if d.first_failed else "none"
            print(
                f"{d.symbol:<10} {d.bias:<8} "
                f"{d.scores['LONG'].total:>7.2f} {d.scores['SHORT'].total:>7.2f} "
                f"{failed:<28} {d.engine_reason}"
            )
        print(f"\nCross-check OK: {sum(1 for d in diagnoses if d.crosscheck_ok)}/{len(diagnoses)}")
        print("Saved: data/diagnostics.json")
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())

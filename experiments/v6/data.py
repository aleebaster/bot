"""Chronologically separated historical window loader (no look-ahead)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.market_data.exchange import ExchangeClient
from app.market_data.models import candles_to_frame


def window_ms(start: str, end: str) -> tuple[int, int]:
    return (
        int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000),
        int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp() * 1000),
    )


async def fetch_window(
    exchange: ExchangeClient,
    symbol: str,
    start_ms: int,
    end_ms: int,
    warmup_days: int = 7,
) -> pd.DataFrame:
    """Fetch [start - warmup, end] so indicators at `start` have past context."""
    since = start_ms - warmup_days * 86_400_000
    unique: dict[int, object] = {}
    while since < end_ms:
        batch = await exchange.fetch_ohlcv(symbol, "15m", limit=1000, since=since)
        if not batch:
            break
        for candle in batch:
            unique[candle.timestamp] = candle
        last = batch[-1].timestamp
        if last >= end_ms or len(batch) < 1000:
            break
        since = last + 900_000
    frame = candles_to_frame([unique[key] for key in sorted(unique)])
    return frame

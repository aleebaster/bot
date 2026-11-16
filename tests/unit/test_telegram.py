"""Telegram formatting and duplicate suppression tests."""

from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.risk_management.position import CostModel, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal
from app.telegram_bot.formatter import format_signal, format_stats, format_tp_hit
from app.telegram_bot.notifier import TelegramNotifier


def make_signal() -> Signal:
    plan = calculate_trade_plan("BTCUSDT", "LONG", 99, 101, 98, [110], 2.0, 1000, 0.005, 1, 2.0, CostModel())
    return Signal(
        symbol="BTCUSDT", direction="LONG", timestamp=1, signal_id="abc123",
        timeframes=["5m", "15m", "1h", "4h"], setup_timeframe="15m", trigger_timeframe="5m",
        plan=plan, score=85, score_breakdown=ScoreBreakdown(multi_timeframe_trend=20, rsi=12),
        rsi14=58.0, trend="BULLISH", atr=2.0, market_context="bullish", reasons=["RSI confirmation"],
        invalidation="close below 98", expiration=2,
    )


def test_format_signal_contains_real_values() -> None:
    text = format_signal(make_signal())
    assert "BTC/USDT" in text
    assert "LONG" in text
    assert "TP1: 102.00000000" in text
    assert "TP2: 104.00000000" in text
    assert "TP3: 110.00000000" in text
    assert "1:5.00" in text
    assert "85.0/100" in text
    assert "RSI confirmation" in text
    assert "Status: ACTIVE" in text


def test_format_tp_hit() -> None:
    assert "TP2 HIT" in format_tp_hit(make_signal(), 2)


def test_format_stats_handles_empty() -> None:
    assert "0" in format_stats({})


@pytest.mark.asyncio
async def test_notifier_deduplicates_without_credentials() -> None:
    notifier = TelegramNotifier(Settings())
    assert await notifier.send_signal(make_signal()) is False  # no bot configured
    assert await notifier.send_signal(make_signal()) is False  # dedup suppressed
    assert len(notifier._seen) == 1

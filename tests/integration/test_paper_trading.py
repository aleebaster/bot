"""Integration: paper trading lifecycle and notifications (no credentials)."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.database.manager import DatabaseManager
from app.database.repository import PaperPositionRepository
from app.risk_management.position import CostModel, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal
from app.telegram_bot.notifier import TelegramNotifier
from app.paper_trading.engine import PaperTradingEngine
from tests.factories import BASE_TS, candle


@pytest.mark.asyncio
async def test_paper_position_opens_and_closes() -> None:
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    notifier = TelegramNotifier(Settings())
    paper = PaperTradingEngine(Settings(paper_trading=True), db, notifier)
    plan = calculate_trade_plan("BTCUSDT", "LONG", 99, 101, 98, [110], 2.0, 1000, 0.005, 1, 2.0, CostModel())
    signal = Signal(
        symbol="BTCUSDT", direction="LONG", timestamp=BASE_TS, signal_id="paper1",
        timeframes=[], setup_timeframe="15m", trigger_timeframe="5m", plan=plan,
        score=85, score_breakdown=ScoreBreakdown(), rsi14=58.0, trend="BULLISH",
        atr=2.0, market_context="bull", expiration=BASE_TS + 10**9,
    )
    try:
        assert await paper.open_from_signal(signal) is True
        assert await paper.open_from_signal(signal) is False
        assert len(await PaperPositionRepository(db).list_open()) == 1

        candles = [candle(BASE_TS, 100, 101, 99, 100), candle(BASE_TS + 1, 100, 102.5, 99, 102)]
        events = await paper.update({"BTCUSDT": candles})
        assert any(e.kind == "TP" for e in events)
        assert len(await PaperPositionRepository(db).list_open()) == 1  # TP1 only: still open

        stop_candle = candle(BASE_TS + 2, 102, 102.5, 97.5, 98)
        events = await paper.update({"BTCUSDT": candles + [stop_candle]})
        assert events
        assert len(await PaperPositionRepository(db).list_open()) == 0  # TP1 locked, SL closes it
    finally:
        await db.close()

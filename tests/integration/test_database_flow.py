"""Integration: database persistence, dedup, tracking and statistics."""

from __future__ import annotations

import pytest

from app.database.manager import DatabaseManager
from app.database.repository import SignalRepository
from app.database.statistics import compute_statistics
from app.database.tracking import TrackingUpdate
from app.risk_management.position import CostModel, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal


def make_signal(signal_id: str, direction: str = "LONG") -> Signal:
    stop = 98 if direction == "LONG" else 102
    targets = [110] if direction == "LONG" else [90]
    low, high = (99, 101)
    plan = calculate_trade_plan("BTCUSDT", direction, low, high, stop, targets, 2.0, 1000, 0.005, 1, 2.0, CostModel())
    return Signal(
        symbol="BTCUSDT", direction=direction, timestamp=1000, signal_id=signal_id,
        timeframes=["5m", "15m", "1h", "4h"], setup_timeframe="15m", trigger_timeframe="5m",
        plan=plan, score=85, score_breakdown=ScoreBreakdown(), rsi14=58.0,
        trend="BULLISH", atr=2.0, market_context="bullish", expiration=100_000_000,
    )


@pytest.mark.asyncio
async def test_database_signal_lifecycle() -> None:
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    repo = SignalRepository(db)
    try:
        signal = make_signal("sig1")
        assert await repo.add(signal) is True
        assert await repo.add(signal) is False  # duplicate suppressed
        assert await repo.exists("sig1") is True
        assert len(await repo.list_recent()) == 1
        assert await repo.count_active() == 1

        await repo.apply_tracking("sig1", TrackingUpdate(outcome="TP3", realized_r=2.9, gross_r=3.0))
        stats = compute_statistics(await repo.all_records())
        assert stats["total_signals"] == 1
        assert stats["wins"] == 1
        assert stats["win_rate"] == 100.0
        assert stats["by_direction"]["LONG"]["signals"] == 1
        assert await repo.count_active() == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sqlite_migration_adds_missing_columns(tmp_path) -> None:
    import sqlite3

    from sqlalchemy import text

    from app.database.manager import DatabaseManager

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, signal_id VARCHAR(32))")
    conn.commit()
    conn.close()

    db = DatabaseManager(f"sqlite+aiosqlite:///{path}")
    await db.init()
    try:
        async with db.engine.begin() as session:
            result = await session.execute(text("PRAGMA table_info(signals)"))
            names = {row[1] for row in result}
        assert {"confirmation_score", "false_signal_risk", "tracking_open", "market_regime"} <= names
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_statistics_include_losses_honestly() -> None:
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    repo = SignalRepository(db)
    try:
        await repo.add(make_signal("win"))
        await repo.add(make_signal("loss", "SHORT"))
        await repo.apply_tracking("win", TrackingUpdate(outcome="TP2", realized_r=1.9))
        await repo.apply_tracking("loss", TrackingUpdate(outcome="SL", realized_r=-1.1))
        stats = compute_statistics(await repo.all_records())
        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["expectancy_r"] == pytest.approx(0.4, abs=0.01)
        assert stats["max_drawdown_r"] < 0
    finally:
        await db.close()

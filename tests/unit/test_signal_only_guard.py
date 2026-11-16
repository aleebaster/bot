"""Guards proving the bot is signal-only and never places exchange orders."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.database.models import SignalRecord
from app.database.statistics import compute_statistics
from app.telegram_bot.notifier import TelegramNotifier
from app.database.tracking import TrackingUpdate
from app.database.repository import SignalRepository
from app.database.manager import DatabaseManager
from app.risk_management.position import CostModel, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal

# Any API that creates/changes/cancels an order or touches real positions.
FORBIDDEN_EXCHANGE_CALLS = {
    "create_order", "create_market_order", "create_limit_order", "create_stop_loss_order",
    "create_take_profit_order", "cancel_order", "cancel_all_orders", "edit_order",
    "set_leverage", "set_margin_mode", "fetch_balance", "fetch_positions",
    "fetch_open_orders", "close_position", "fetch_deposit_address", "withdraw",
}


def test_no_trading_api_calls_in_source() -> None:
    root = Path(__file__).resolve().parents[2] / "app"
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_EXCHANGE_CALLS:
                violations.append(f"{path.relative_to(root)}:{node.lineno} {node.attr}")
    assert violations == [], f"Trading API calls found: {violations}"


def test_signal_only_defaults(monkeypatch) -> None:
    # .env is git-ignored and may exist locally; isolate the default check.
    monkeypatch.delenv("SIGNAL_ONLY", raising=False)
    monkeypatch.delenv("PAPER_TRADING", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    settings = Settings.from_env()
    assert settings.signal_only is True
    assert settings.paper_trading is False
    assert settings.dry_run is True


def test_stats_ignore_unresolved_open_signals() -> None:
    """Future/unclosed outcomes must not leak into statistics."""
    from datetime import datetime, timezone

    record = SignalRecord(
        signal_id="open-1", symbol="BTCUSDT", direction="LONG", timestamp=1000,
        entry=100.0, entry_low=99.0, entry_high=101.0, stop_loss=98.0,
        tp1=102.0, tp2=104.0, tp3=106.0, risk_reward=3.0, score=85.0,
        realized_r=999.0,  # deliberately extreme: must be ignored while OPEN
        outcome="OPEN", status="ACTIVE", risk_usdt=5.0,
        created_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    stats = compute_statistics([record])
    assert stats["total_signals"] == 0
    assert stats["expectancy_r"] == 0.0
    assert stats["profit_factor"] == 0.0


@pytest.mark.asyncio
async def test_signal_stored_without_paper_position_in_signal_only_mode() -> None:
    from app.paper_trading.engine import PaperTradingEngine
    from app.database.repository import PaperPositionRepository

    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    settings = Settings(paper_trading=False)
    paper = PaperTradingEngine(settings, db, TelegramNotifier(settings))
    plan = calculate_trade_plan("BTCUSDT", "LONG", 99, 101, 98, [110], 2.0, 1000, 0.005, 1, 2.0, CostModel())
    signal = Signal(
        symbol="BTCUSDT", direction="LONG", timestamp=1000, signal_id="only-1",
        timeframes=[], setup_timeframe="15m", trigger_timeframe="5m", plan=plan,
        score=85, score_breakdown=ScoreBreakdown(), rsi14=55.0, trend="BULLISH",
        atr=2.0, market_context="test", expiration=10**12,
    )
    try:
        assert await paper.open_from_signal(signal) is True
        assert len(await PaperPositionRepository(db).list_open()) == 0
        assert len(await paper.signals.list_open()) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_telegram_retries_then_succeeds() -> None:
    class FlakyBot:
        def __init__(self):
            self.calls = 0

        async def send_message(self, chat_id, text):
            self.calls += 1
            if self.calls < 3:
                raise TimeoutError("temporary")
            return None

    bot = FlakyBot()
    notifier = TelegramNotifier(Settings(telegram_chat_id="1"), bot=bot)
    assert await notifier.send("test") is True
    assert bot.calls == 3

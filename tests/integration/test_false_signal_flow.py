"""Integration: false-signal evaluation -> Signal -> DB -> stats -> Telegram."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.constants import LONG
from app.database.manager import DatabaseManager
from app.database.repository import SignalRepository
from app.database.statistics import compute_statistics
from app.database.tracking import TrackingUpdate
from app.false_signal.engine import FalseSignalEngine, format_rejected_from_dict
from app.false_signal.models import (
    BreakoutVerdict,
    CandleConfirmationResult,
    ConfirmationScore,
    ConfirmationVerdict,
    EntryLocation,
    EntryQualityResult,
    EntryVerdict,
    FalseBreakoutResult,
    FalseSignalRisk,
    LiquidityTrapResult,
    MTFConfirmationResult,
    RSIConfirmationResult,
    RecheckResult,
    VolumeConfirmationResult,
)
from app.risk_management.position import CostModel, calculate_trade_plan
from app.signal_engine.models import ScoreBreakdown, Signal
from app.telegram_bot.formatter import format_signal
from tests.factories import make_frames


def make_plan():
    return calculate_trade_plan(
        "BTCUSDT", LONG, 99, 101, 98, [110], 2.0, 1000, 0.005, 1, 2.0, CostModel()
    )


def make_verdict(verdict=EntryVerdict.EARLY_ENTRY, score=72, risk=45):
    return ConfirmationVerdict(
        verdict=verdict,
        confirmation=ConfirmationScore(multi_timeframe=score),
        risk=FalseSignalRisk(score=risk),
        entry_location=EntryQualityResult(location=EntryLocation.EARLY_ENTRY),
        breakout=FalseBreakoutResult(verdict=BreakoutVerdict.NO_BREAKOUT),
        trap=LiquidityTrapResult(),
        rsi=RSIConfirmationResult(),
        candle=CandleConfirmationResult(closed=True),
        volume=VolumeConfirmationResult(),
        mtf=MTFConfirmationResult(),
        reasons_confirm=["Trend alignment"],
        reasons_reject=["Late entry"],
        decision="WAIT FOR CONFIRMATION",
    )


def test_full_evaluation_is_serialisable() -> None:
    frames = make_frames()
    settings = Settings()
    verdict = FalseSignalEngine(settings).evaluate(
        "BTCUSDT", LONG, frames, make_plan(), now_ms=int(frames["5m"]["timestamp"].iloc[-1]) + 1000
    )
    data = verdict.as_dict()
    assert "confirmation_score" in data
    assert "false_signal_risk" in data
    assert 0 <= data["confirmation_score"] <= 100
    assert 0 <= data["false_signal_risk"] <= 100
    assert isinstance(data["hard_blocks"], list)
    assert data["verdict"] in {v.value for v in EntryVerdict}


@pytest.mark.asyncio
async def test_confirmation_persists_and_stats_split_by_status() -> None:
    db = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await db.init()
    repo = SignalRepository(db)
    try:
        verdict = make_verdict(EntryVerdict.STRONG_ENTRY, 92, 12)
        signal = Signal(
            symbol="BTCUSDT", direction=LONG, timestamp=1000, signal_id="conf-1",
            timeframes=["5m", "15m", "1h", "4h"], setup_timeframe="15m", trigger_timeframe="5m",
            plan=make_plan(), score=85, score_breakdown=ScoreBreakdown(), rsi14=55.0,
            trend="BULLISH", atr=2.0, market_context="test", confirmation=verdict.as_dict(),
            confirmation_status=verdict.verdict.value, false_signal_risk=verdict.risk.score,
        )
        assert await repo.add(signal)
        await repo.apply_tracking("conf-1", TrackingUpdate(outcome="TP3", realized_r=2.9))
        await repo.log_rejection("ETHUSDT", LONG, {
            "verdict": "FALSE BREAKOUT", "false_signal_risk": 78,
            "reasons_reject": ["False breakout detected"],
        })
        stats = compute_statistics(await repo.all_records(), await repo.all_rejections())
        assert stats["total_rejections"] == 1
        assert stats["false_breakout_rate"] == 100.0
        assert "STRONG ENTRY" in stats["by_confirmation_status"]
        assert "countertrend" in stats
        assert "by_false_signal_risk" in stats
    finally:
        await db.close()


def test_telegram_shows_entry_quality_and_rejection_detail() -> None:
    verdict = make_verdict(EntryVerdict.STRONG_ENTRY, 92, 12)
    signal = Signal(
        symbol="BTCUSDT", direction=LONG, timestamp=1000, signal_id="conf-2",
        timeframes=["5m", "15m", "1h", "4h"], setup_timeframe="15m", trigger_timeframe="5m",
        plan=make_plan(), score=85, score_breakdown=ScoreBreakdown(), rsi14=55.0,
        trend="BULLISH", atr=2.0, market_context="test", confirmation=verdict.as_dict(),
        confirmation_status=verdict.verdict.value,
    )
    text = format_signal(signal)
    assert "🧠 ENTRY QUALITY" in text
    assert "Confirmation Score: 92.0/100" in text
    assert "False Signal Risk: 12/100" in text
    assert "Decision: WAIT FOR CONFIRMATION" in text

    rejected = make_verdict(EntryVerdict.FALSE_BREAKOUT, 60, 78)
    rejected.reasons_reject = ["False breakout detected.", "RSI momentum disagreement."]
    text = format_rejected_from_dict("ETHUSDT", LONG, rejected.as_dict())
    assert "SIGNAL REJECTED" in text
    assert "False breakout detected." in text
    assert "Decision: NO TRADE." in text


def test_recheck_early_to_confirmed_and_invalidated(monkeypatch) -> None:
    settings = Settings()
    engine = FalseSignalEngine(settings)
    frames = make_frames()
    plan = make_plan()

    monkeypatch.setattr(engine, "evaluate", lambda *a, **kw: make_verdict(EntryVerdict.CONFIRMED_ENTRY, 88, 20))
    confirmed = engine.recheck("BTCUSDT", "id", EntryVerdict.EARLY_ENTRY, LONG, frames, plan)
    assert confirmed.confirmed and not confirmed.invalidated
    assert confirmed.new_verdict == EntryVerdict.CONFIRMED_ENTRY

    bad = make_verdict(EntryVerdict.WEAK_SIGNAL, 50, 80)
    bad.hard_blocks = ["Structure broken"]
    monkeypatch.setattr(engine, "evaluate", lambda *a, **kw: bad)
    invalidated = engine.recheck("BTCUSDT", "id", EntryVerdict.EARLY_ENTRY, LONG, frames, plan)
    assert invalidated.invalidated
    assert invalidated.new_verdict == EntryVerdict.INVALIDATED

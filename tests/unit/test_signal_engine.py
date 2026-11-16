"""Signal engine hard filters and NO TRADE behaviour."""

from __future__ import annotations

from app.config import Settings
from app.constants import LONG
from app.risk_management.manager import RiskManager
from app.signal_engine.engine import SignalEngine
from app.signal_engine.models import EngineResult, ScoreBreakdown, make_signal_id
from tests.factories import make_frames


def engine(**settings) -> SignalEngine:
    return SignalEngine(Settings(**settings), RiskManager(Settings()))


def test_no_trade_on_missing_frames() -> None:
    result = engine().generate("BTCUSDT", {})
    assert result.signal is None
    assert "history" in result.reason.lower()


def test_no_trade_on_stale_data() -> None:
    frames = make_frames()
    now = int(frames["5m"]["timestamp"].iloc[-1]) + 10_000_000
    result = engine().generate("BTCUSDT", frames, {"now_ms": now})
    assert not result.is_trade
    assert "stale" in result.reason.lower()


def test_no_trade_on_open_candle() -> None:
    frames = make_frames()
    last = frames["5m"]["timestamp"].iloc[-1]
    frames["5m"].loc[frames["5m"]["timestamp"] == last, "closed"] = False
    result = engine().generate("BTCUSDT", frames, {"now_ms": int(last) + 1000})
    assert not result.is_trade
    assert "unconfirmed" in result.reason.lower()


def test_signal_id_is_deterministic() -> None:
    a = make_signal_id("BTCUSDT", LONG, 1000, 100.1234567)
    b = make_signal_id("BTCUSDT", LONG, 1000, 100.1234567)
    assert a == b and len(a) == 16


def test_engine_returns_engine_result_type() -> None:
    result = engine().generate("BTCUSDT", make_frames())
    assert isinstance(result, EngineResult)
    assert result.score >= 0

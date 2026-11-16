"""Signal domain models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.constants import SCORE_EXCELLENT, SCORE_MODERATE, SCORE_STRONG
from app.risk_management.position import TradePlan


@dataclass
class ScoreBreakdown:
    multi_timeframe_trend: float = 0.0
    rsi: float = 0.0
    candlestick: float = 0.0
    market_structure: float = 0.0
    support_resistance: float = 0.0
    volume: float = 0.0
    ema_vwap: float = 0.0
    volatility_entry: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.multi_timeframe_trend
            + self.rsi
            + self.candlestick
            + self.market_structure
            + self.support_resistance
            + self.volume
            + self.ema_vwap
            + self.volatility_entry,
            2,
        )

    @property
    def category(self) -> str:
        total = self.total
        if total >= SCORE_EXCELLENT:
            return "Excellent"
        if total >= SCORE_STRONG:
            return "Strong"
        if total >= SCORE_MODERATE:
            return "Moderate"
        return "Ignore"

    def as_dict(self) -> dict[str, float]:
        return {
            "multi_timeframe_trend": self.multi_timeframe_trend,
            "rsi": self.rsi,
            "candlestick": self.candlestick,
            "market_structure": self.market_structure,
            "support_resistance": self.support_resistance,
            "volume": self.volume,
            "ema_vwap": self.ema_vwap,
            "volatility_entry": self.volatility_entry,
            "total": self.total,
        }


@dataclass
class Signal:
    symbol: str
    direction: str
    timestamp: int
    signal_id: str
    timeframes: list[str]
    setup_timeframe: str
    trigger_timeframe: str
    plan: TradePlan
    score: float
    score_breakdown: ScoreBreakdown
    rsi14: float | None
    trend: str
    atr: float
    market_context: str
    reasons: list[str] = field(default_factory=list)
    invalidation: str = ""
    funding_rate: float | None = None
    open_interest: float | None = None
    expiration: int = 0
    status: str = "ACTIVE"
    # Populated by the optional False Signal Detection Engine. Defaults keep
    # all existing Signal construction sites valid.
    confirmation: dict | None = None
    confirmation_status: str = ""
    false_signal_risk: int = 0
    countertrend: bool = False
    current_price: float = 0.0

    @property
    def entry(self) -> float:
        return self.plan.entry

    @property
    def stop_loss(self) -> float:
        return self.plan.stop_loss

    @property
    def tp1(self) -> float:
        return self.plan.tp1

    @property
    def tp2(self) -> float:
        return self.plan.tp2

    @property
    def tp3(self) -> float:
        return self.plan.tp3

    @property
    def risk_reward(self) -> float:
        return self.plan.risk_reward


@dataclass
class EngineResult:
    signal: Signal | None
    reason: str = ""
    score: float = 0.0
    category: str = "Ignore"
    diagnostics: dict[str, object] = field(default_factory=dict)

    @property
    def is_trade(self) -> bool:
        return self.signal is not None


def make_signal_id(symbol: str, direction: str, trigger_timestamp: int, entry: float) -> str:
    """Stable id used by the database and Telegram notifier for dedup."""
    raw = f"{symbol}|{direction}|{trigger_timestamp}|{round(entry, 6)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

"""Domain models for false-signal detection and entry confirmation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class EntryVerdict(str, Enum):
    STRONG_ENTRY = "STRONG ENTRY"
    CONFIRMED_ENTRY = "CONFIRMED ENTRY"
    EARLY_ENTRY = "EARLY ENTRY"
    WEAK_SIGNAL = "WEAK SIGNAL"
    FALSE_BREAKOUT = "FALSE BREAKOUT"
    LIQUIDITY_TRAP = "LIQUIDITY TRAP"
    INVALIDATED = "INVALIDATED"
    NO_TRADE = "NO TRADE"


class BreakoutVerdict(str, Enum):
    CONFIRMED_BREAKOUT = "CONFIRMED BREAKOUT"
    FAILED_BREAKOUT = "FAILED BREAKOUT"
    BREAKOUT_RETEST = "BREAKOUT RETEST"
    LIQUIDITY_SWEEP = "LIQUIDITY SWEEP"
    STOP_HUNT_CANDIDATE = "STOP HUNT CANDIDATE"
    NO_BREAKOUT = "NO BREAKOUT"


class EntryLocation(str, Enum):
    GOOD_ENTRY_ZONE = "GOOD ENTRY ZONE"
    LATE_ENTRY = "LATE ENTRY"
    EARLY_ENTRY = "EARLY ENTRY"
    WAIT_FOR_RETEST = "WAIT FOR RETEST"
    ENTRY_INVALIDATED = "ENTRY INVALIDATED"


class MTFAlignment(str, Enum):
    FULL = "FULL TREND ALIGNMENT"
    PARTIAL = "PARTIAL TREND ALIGNMENT"
    CONFLICT = "TIMEFRAME CONFLICT"
    COUNTERTREND = "COUNTERTREND SETUP"
    REVERSAL = "TREND REVERSAL CANDIDATE"


class ConfidenceCategory(str, Enum):
    STRONG = "STRONG"
    CONFIRMED = "CONFIRMED"
    EARLY = "EARLY / WAIT"
    WEAK = "WEAK"


class RiskCategory(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    ELEVATED = "Elevated"
    HIGH = "High"
    VERY_HIGH = "Very High"


@dataclass(frozen=True)
class Finding:
    """A single detected phenomenon with its confirmation strength."""

    name: str
    strength: float  # 0..1
    detail: str
    bars_ago: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class FalseBreakoutResult:
    verdict: BreakoutVerdict
    level: float | None = None
    closed_beyond: bool = False
    holds_level: bool = False
    retest: bool = False
    returned_inside: bool = False
    rejection_wick: bool = False
    volume_confirmed: bool = False
    short_lived: bool = False
    findings: list[Finding] = field(default_factory=list)
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.verdict in {BreakoutVerdict.FAILED_BREAKOUT, BreakoutVerdict.STOP_HUNT_CANDIDATE}

    @property
    def is_sweep(self) -> bool:
        return self.verdict in {BreakoutVerdict.LIQUIDITY_SWEEP, BreakoutVerdict.STOP_HUNT_CANDIDATE}


@dataclass
class LiquidityTrapResult:
    detected: bool = False
    strength: float = 0.0
    findings: list[Finding] = field(default_factory=list)
    detail: str = ""

    @property
    def strong(self) -> bool:
        return self.detected and self.strength >= 0.6


@dataclass
class RSIConfirmationResult:
    bullish_confirmation: bool = False
    bearish_confirmation: bool = False
    divergence_warning: bool = False
    momentum_weakness: bool = False
    false_breakout_warning: bool = False
    agreement: float = 0.0  # -1 (conflicts) .. +1 (fully agrees)
    score: float = 0.0  # 0..15
    findings: list[Finding] = field(default_factory=list)
    detail: str = ""


@dataclass
class CandleConfirmationResult:
    confirmed: bool = False
    closed: bool = True
    body_ok: bool = False
    volume_ok: bool = False
    direction_match: bool = False
    near_level: bool = False
    next_bar_confirms: bool = False
    patterns: list[str] = field(default_factory=list)
    score: float = 0.0  # 0..15
    detail: str = ""


@dataclass
class VolumeConfirmationResult:
    relative_volume: float = 0.0
    spike: bool = False
    expansion: bool = False
    divergence: bool = False
    breakout_volume: bool = False
    rejection_volume: bool = False
    weak_participation: bool = False
    score: float = 0.0  # 0..10
    detail: str = ""


@dataclass
class MTFConfirmationResult:
    alignment: MTFAlignment = MTFAlignment.PARTIAL
    score: float = 0.0  # 0..20
    countertrend: bool = False
    directions: dict[str, str] = field(default_factory=dict)
    detail: str = ""


@dataclass
class EntryQualityResult:
    location: EntryLocation = EntryLocation.EARLY_ENTRY
    score: float = 0.0  # 0..10
    distance_to_entry_atr: float = 0.0
    extension_atr: float = 0.0
    impulse_consumed_pct: float = 0.0
    stop_atr_multiple: float = 0.0
    risk_reward: float = 0.0
    mid_range: bool = False
    prefer_retest: bool = False
    detail: str = ""


@dataclass
class ConfirmationScore:
    multi_timeframe: float = 0.0  # max 20
    price_action: float = 0.0  # max 15
    rsi: float = 0.0  # max 15
    candle: float = 0.0  # max 15
    volume: float = 0.0  # max 10
    breakout: float = 0.0  # max 10
    entry_location: float = 0.0  # max 10
    volatility: float = 0.0  # max 5

    @property
    def total(self) -> float:
        return round(sum(self.as_dict().values()), 2)

    @property
    def category(self) -> ConfidenceCategory:
        t = self.total
        if t >= 90:
            return ConfidenceCategory.STRONG
        if t >= 80:
            return ConfidenceCategory.CONFIRMED
        if t >= 70:
            return ConfidenceCategory.EARLY
        return ConfidenceCategory.WEAK

    def as_dict(self) -> dict[str, float]:
        return {
            "multi_timeframe": self.multi_timeframe,
            "price_action": self.price_action,
            "rsi": self.rsi,
            "candle": self.candle,
            "volume": self.volume,
            "breakout": self.breakout,
            "entry_location": self.entry_location,
            "volatility": self.volatility,
        }


@dataclass
class FalseSignalRisk:
    score: int = 0  # 0..100
    contributors: list[Finding] = field(default_factory=list)

    @property
    def category(self) -> RiskCategory:
        s = self.score
        if s <= 20:
            return RiskCategory.LOW
        if s <= 40:
            return RiskCategory.MODERATE
        if s <= 60:
            return RiskCategory.ELEVATED
        if s <= 80:
            return RiskCategory.HIGH
        return RiskCategory.VERY_HIGH


@dataclass
class ConfirmationVerdict:
    verdict: EntryVerdict
    confirmation: ConfirmationScore
    risk: FalseSignalRisk
    entry_location: EntryQualityResult
    breakout: FalseBreakoutResult
    trap: LiquidityTrapResult
    rsi: RSIConfirmationResult
    candle: CandleConfirmationResult
    volume: VolumeConfirmationResult
    mtf: MTFConfirmationResult
    reasons_confirm: list[str] = field(default_factory=list)
    reasons_reject: list[str] = field(default_factory=list)
    hard_blocks: list[str] = field(default_factory=list)
    countertrend: bool = False
    decision: str = "NO TRADE"

    @property
    def approved(self) -> bool:
        return self.verdict in {
            EntryVerdict.STRONG_ENTRY,
            EntryVerdict.CONFIRMED_ENTRY,
            EntryVerdict.EARLY_ENTRY,
        }

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "decision": self.decision,
            "confirmation_score": self.confirmation.total,
            "confirmation_category": self.confirmation.category.value,
            "confirmation_components": self.confirmation.as_dict(),
            "false_signal_risk": self.risk.score,
            "risk_category": self.risk.category.value,
            "risk_contributors": [f.as_dict() for f in self.risk.contributors],
            "entry_location": self.entry_location.location.value,
            "reasons_confirm": self.reasons_confirm,
            "reasons_reject": self.reasons_reject,
            "hard_blocks": self.hard_blocks,
            "countertrend": self.countertrend,
            "breakout_verdict": self.breakout.verdict.value,
            "trap_strength": round(self.trap.strength, 3),
        }


@dataclass
class RecheckResult:
    signal_id: str
    previous_verdict: EntryVerdict
    new_verdict: EntryVerdict
    confirmed: bool
    invalidated: bool
    reasons: list[str] = field(default_factory=list)
    closed_bar_ts: int = 0

    def as_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "previous_verdict": self.previous_verdict.value,
            "new_verdict": self.new_verdict.value,
            "confirmed": self.confirmed,
            "invalidated": self.invalidated,
            "reasons": self.reasons,
            "closed_bar_ts": self.closed_bar_ts,
        }

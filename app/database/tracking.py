"""Signal outcome tracking with chronological SL/TP resolution and MFE/MAE."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.market_data.models import Candle
from app.risk_management.position import CostModel
from app.signal_engine.models import Signal

CLOSED_OUTCOMES = {"SL", "TP1", "TP2", "TP3", "EXPIRED", "INVALIDATED"}


@dataclass(frozen=True)
class TrackedSetup:
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_usdt: float
    notional: float
    expiration: int
    timestamp: int

    @classmethod
    def from_signal(cls, signal: Signal) -> TrackedSetup:
        return cls(
            symbol=signal.symbol,
            direction=signal.direction,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            risk_usdt=signal.plan.risk_usdt,
            notional=signal.plan.notional,
            expiration=signal.expiration,
            timestamp=signal.timestamp,
        )

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop_loss)


@dataclass
class TrackingUpdate:
    outcome: str = "OPEN"
    realized_r: float = 0.0  # net of fees, expressed in R
    gross_r: float = 0.0
    mfe: float = 0.0
    mae: float = 0.0
    fees: float = 0.0
    highest_tp: int = 0
    events: list[str] = field(default_factory=list)
    exit_price: float | None = None
    closed_at: int | None = None

    @property
    def is_closed(self) -> bool:
        return self.outcome in CLOSED_OUTCOMES


class SignalTracker:
    """Walk candles in time order and resolve the first triggered event.

    Conservative rules (documented in docs/STRATEGY.md):
      * Within a single candle where both SL and TP are touched, SL wins.
      * After TP1 the simulated stop moves to breakeven; after TP2 the R outcome
        is locked at +1R. This is deliberate and never optimistic.
      * R values are reported net of the estimated trading costs.
    """

    def __init__(self, cost_model: CostModel) -> None:
        self.cost_model = cost_model

    def track(self, setup: TrackedSetup, candles: list[Candle], holding_bars_1h: int = 8) -> TrackingUpdate:
        update = TrackingUpdate()
        if setup.risk_per_unit <= 0:
            return update
        fees = self.cost_model.round_trip_cost(setup.notional, holding_bars_1h)
        fee_r = fees / setup.risk_usdt if setup.risk_usdt > 0 else 0.0
        update.fees = fees
        sign = 1 if setup.direction == "LONG" else -1
        risk = setup.risk_per_unit

        for candle in sorted((c for c in candles if c.timestamp >= setup.timestamp), key=lambda c: c.timestamp):
            if sign > 0:
                favorable = (candle.high - setup.entry) / risk
                adverse = (setup.entry - candle.low) / risk
            else:
                favorable = (setup.entry - candle.low) / risk
                adverse = (candle.high - setup.entry) / risk
            update.mfe = max(update.mfe, favorable)
            update.mae = max(update.mae, adverse)

            sl_touched = candle.low <= setup.stop_loss <= candle.high
            tp1_touched = (candle.high >= setup.tp1) if sign > 0 else (candle.low <= setup.tp1)
            tp2_touched = (candle.high >= setup.tp2) if sign > 0 else (candle.low <= setup.tp2)
            tp3_touched = (candle.high >= setup.tp3) if sign > 0 else (candle.low <= setup.tp3)

            # SL has priority inside a single bar.
            if sl_touched and update.highest_tp == 0:
                update.outcome = "SL"
                update.gross_r = -1.0
                update.realized_r = round(-1.0 - fee_r, 4)
                update.exit_price = setup.stop_loss
                update.closed_at = candle.timestamp
                update.events.append("SL")
                return update

            if not sl_touched:
                if tp3_touched:
                    update.highest_tp = 3
                    update.outcome = "TP3"
                    update.gross_r = 3.0
                    update.exit_price = setup.tp3
                    update.events.append("TP3")
                elif tp2_touched:
                    update.highest_tp = 2
                    update.outcome = "TP2"
                    update.gross_r = 1.0
                    update.exit_price = setup.tp2
                    update.events.append("TP2")
                elif tp1_touched:
                    update.highest_tp = 1
                    update.outcome = "TP1"
                    update.gross_r = 0.0
                    update.exit_price = setup.tp1
                    update.events.append("TP1")

            if update.highest_tp and sl_touched:
                # Partial target was hit first; the remaining position is closed
                # by the (possibly breakeven) stop. Outcome records the partial.
                update.outcome = {1: "TP1", 2: "TP2", 3: "TP3"}[update.highest_tp]
                update.closed_at = candle.timestamp
                update.realized_r = round(update.gross_r - fee_r, 4)
                return update
            if update.highest_tp == 3:
                update.closed_at = candle.timestamp
                update.realized_r = round(update.gross_r - fee_r, 4)
                return update

            # End of bar: TP1/TP2 levels are considered but the position remains
            # open until SL (breakeven after TP1) or TP3 is reached.
            if update.highest_tp in (1, 2):
                update.realized_r = round(update.gross_r - fee_r, 4)
                update.outcome = "OPEN"

        if candles and candles[-1].timestamp >= setup.expiration:
            update.outcome = "EXPIRED"
            update.closed_at = candles[-1].timestamp
            update.realized_r = round(update.gross_r - fee_r, 4)
        return update

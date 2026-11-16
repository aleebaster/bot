"""Paper trading simulator. Opens simulated positions only; never sends orders."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import Settings
from app.database.manager import DatabaseManager
from app.database.models import PaperPosition, SignalRecord
from app.database.repository import PaperPositionRepository, SignalRepository
from app.database.statistics import compute_statistics
from app.database.tracking import SignalTracker, TrackedSetup, TrackingUpdate
from app.market_data.models import Candle
from app.risk_management.position import CostModel, TradePlan
from app.signal_engine.models import ScoreBreakdown, Signal
from app.telegram_bot.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def _signal_from_record(record: SignalRecord, margin: float = 0.0) -> Signal:
    """Reconstruct a Signal from a stored record for notification formatting."""
    plan = TradePlan(
        symbol=record.symbol,
        direction=record.direction,
        entry_low=record.entry_low,
        entry_high=record.entry_high,
        entry=record.entry,
        stop_loss=record.stop_loss,
        tp1=record.tp1,
        tp2=record.tp2,
        tp3=record.tp3,
        risk_reward=record.risk_reward,
        atr=0.0,
        stop_distance=abs(record.entry - record.stop_loss),
        stop_atr_multiple=0.0,
        position_size=record.position_size,
        notional=record.notional,
        margin=margin,
        risk_usdt=record.risk_usdt,
        estimated_cost=record.estimated_cost,
    )
    return Signal(
        symbol=record.symbol,
        direction=record.direction,
        timestamp=record.timestamp,
        signal_id=record.signal_id,
        timeframes=[],
        setup_timeframe=record.setup_timeframe,
        trigger_timeframe=record.trigger_timeframe,
        plan=plan,
        score=record.score,
        score_breakdown=ScoreBreakdown(),
        rsi14=record.rsi14,
        trend=record.market_context,
        atr=0.0,
        market_context=record.market_context,
        invalidation=record.invalidation,
        expiration=record.expiration,
        status=record.status,
    )


@dataclass
class PaperEvent:
    kind: str
    symbol: str
    signal_id: str
    detail: str


class PaperTradingEngine:
    """Simulates fills and tracks TP/SL outcomes using the shared SignalTracker."""

    def __init__(self, settings: Settings, db: DatabaseManager, notifier: TelegramNotifier) -> None:
        self.settings = settings
        self.db = db
        self.notifier = notifier
        self.positions = PaperPositionRepository(db)
        self.signals = SignalRepository(db)
        self.tracker = SignalTracker(
            CostModel(
                taker_fee=settings.taker_fee,
                maker_fee=settings.maker_fee,
                slippage=settings.slippage,
                funding_per_8h=settings.funding_per_8h,
                max_holding_bars=settings.max_holding_bars_for_funding,
            )
        )

    async def open_from_signal(self, signal: Signal) -> bool:
        """Open a simulated position and persist the originating signal."""
        await self.signals.add(signal)
        if not self.settings.paper_trading:
            logger.info("Paper trading disabled - signal stored but not simulated")
            return False
        if not await self.positions.open(signal):
            logger.info("Paper position already exists: %s", signal.signal_id)
            return False
        logger.info("Opened PAPER %s %s %s (id=%s)", signal.symbol, signal.direction, signal.entry, signal.signal_id)
        return True

    async def update(
        self, candles_by_symbol: dict[str, list[Candle]]
    ) -> list[PaperEvent]:
        """Advance all open paper positions with the latest closed candles."""
        events: list[PaperEvent] = []
        for position in await self.positions.list_open():
            candles = candles_by_symbol.get(position.symbol, [])
            if not candles:
                continue
            setup = TrackedSetup(
                symbol=position.symbol,
                direction=position.direction,
                entry=position.entry,
                stop_loss=position.stop_loss,
                tp1=position.tp1,
                tp2=position.tp2,
                tp3=position.tp3,
                risk_usdt=self._risk_usdt(position),
                notional=position.notional,
                expiration=1 << 60,  # explicit expiry is handled by the scheduler
                timestamp=position.opened_at,
            )
            update = self.tracker.track(setup, candles)
            await self.signals.apply_tracking(position.signal_id, update)
            await self._update_position(position, update)
            events.extend(await self._notify(position, update))
        return events

    @staticmethod
    def _risk_usdt(position: PaperPosition) -> float:
        return abs(position.entry - position.stop_loss) * position.size

    async def _update_position(self, position: PaperPosition, update: TrackingUpdate) -> None:
        pnl = update.realized_r * self._risk_usdt(position)
        closed = update.is_closed
        fields: dict[str, object] = {
            "mfe": update.mfe,
            "mae": update.mae,
            "realized_r": update.realized_r,
            "pnl_usdt": pnl,
            "tp1_hit": int(update.highest_tp >= 1),
            "tp2_hit": int(update.highest_tp >= 2),
            "tp3_hit": int(update.highest_tp >= 3),
        }
        if closed:
            fields.update(
                status="CLOSED",
                closed_at=update.closed_at,
                exit_price=update.exit_price,
            )
        await self.positions.update(position, **fields)

    async def _notify(self, position: PaperPosition, update: TrackingUpdate) -> list[PaperEvent]:
        events: list[PaperEvent] = []
        record = SignalRecord(
            symbol=position.symbol,
            direction=position.direction,
            timestamp=position.opened_at,
            signal_id=position.signal_id,
            entry=position.entry,
            entry_low=position.entry,
            entry_high=position.entry,
            stop_loss=position.stop_loss,
            tp1=position.tp1,
            tp2=position.tp2,
            tp3=position.tp3,
            risk_reward=0.0,
            score=0.0,
            setup_timeframe="15m",
            trigger_timeframe="5m",
            position_size=position.size,
            notional=position.notional,
            risk_usdt=self._risk_usdt(position),
            estimated_cost=position.fees,
            market_context="Paper position",
        )
        signal = _signal_from_record(record, margin=position.margin)
        for event in update.events:
            if event.startswith("TP"):
                level = int(event[2:])
                await self.notifier.tp_hit(signal, level)
                events.append(PaperEvent("TP", position.symbol, position.signal_id, f"TP{level}"))
        if update.outcome == "SL":
            await self.notifier.stop_loss(signal)
            events.append(PaperEvent("SL", position.symbol, position.signal_id, "Stop loss"))
        elif update.outcome == "EXPIRED":
            await self.notifier.expired(signal)
            events.append(PaperEvent("EXPIRED", position.symbol, position.signal_id, "Expired"))
        return events

    async def daily_report(self) -> dict:
        stats = compute_statistics(await self.signals.all_records(), await self.signals.all_rejections())
        logger.info("Daily paper report: %d closed signals, PF=%s", stats["total_signals"], stats["profit_factor"])
        return stats

"""Repositories for signal records, paper positions and daily reports."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.database.manager import DatabaseManager
from app.database.models import DailyReport, PaperPosition, RejectionRecord, SignalRecord
from app.signal_engine.models import Signal
from app.database.tracking import TrackingUpdate

logger = logging.getLogger(__name__)


class SignalRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def exists(self, signal_id: str) -> bool:
        async with self.db.session() as session:
            result = await session.execute(select(SignalRecord.id).where(SignalRecord.signal_id == signal_id))
            return result.first() is not None

    async def add(self, signal: Signal) -> bool:
        """Persist a signal. Returns False when a duplicate id already exists."""
        if await self.exists(signal.signal_id):
            logger.info("Duplicate signal suppressed: %s", signal.signal_id)
            return False
        now = int(time.time() * 1000)
        record = SignalRecord(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            direction=signal.direction,
            timestamp=signal.timestamp,
            entry_low=signal.plan.entry_low,
            entry_high=signal.plan.entry_high,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            risk_reward=signal.risk_reward,
            score=signal.score,
            rsi14=signal.rsi14,
            market_context=signal.market_context,
            reasons=json.dumps(signal.reasons),
            invalidation=signal.invalidation,
            setup_timeframe=signal.setup_timeframe,
            trigger_timeframe=signal.trigger_timeframe,
            funding_rate=signal.funding_rate,
            open_interest=signal.open_interest,
            position_size=signal.plan.position_size,
            notional=signal.plan.notional,
            risk_usdt=signal.plan.risk_usdt,
            estimated_cost=signal.plan.estimated_cost,
            expiration=signal.expiration,
            status=signal.status,
            confirmation_score=float((signal.confirmation or {}).get("confirmation_score", 0.0)),
            false_signal_risk=int((signal.confirmation or {}).get("false_signal_risk", 0)),
            confirmation_status=signal.confirmation_status,
            confirmation_reasons=json.dumps((signal.confirmation or {}).get("reasons_confirm", [])),
            rejection_reasons=json.dumps((signal.confirmation or {}).get("reasons_reject", [])),
            entry_location=(signal.confirmation or {}).get("entry_location", ""),
            countertrend=int(signal.countertrend),
            tracking_open=1,
            outcome="OPEN",
            created_at=now,
            updated_at=now,
        )
        async with self.db.session() as session:
            session.add(record)
            await session.commit()
        return True

    async def apply_tracking(self, signal_id: str, update_data: TrackingUpdate) -> None:
        outcome = update_data.outcome
        status = {
            "OPEN": "ACTIVE",
            "TP1": "TP1 HIT",
            "TP2": "TP2 HIT",
            "TP3": "TP3 HIT",
            "SL": "SL HIT",
            "EXPIRED": "EXPIRED",
        }.get(outcome, "ACTIVE")
        still_open = outcome in {"OPEN", "TP1", "TP2"}
        async with self.db.session() as session:
            await session.execute(
                update(SignalRecord)
                .where(SignalRecord.signal_id == signal_id)
                .values(
                    outcome=outcome,
                    status=status,
                    tracking_open=int(still_open),
                    realized_r=update_data.realized_r,
                    gross_r=update_data.gross_r,
                    mfe=update_data.mfe,
                    mae=update_data.mae,
                    fees=update_data.fees,
                    highest_tp=update_data.highest_tp,
                    updated_at=int(time.time() * 1000),
                )
            )
            await session.commit()

    async def log_rejection(self, symbol: str, direction: str, data: dict) -> None:
        """Persist a filtered idea so rejection frequency can be measured."""
        async with self.db.session() as session:
            session.add(
                RejectionRecord(
                    symbol=symbol,
                    direction=direction,
                    timestamp=data.get("timestamp") or int(time.time() * 1000),
                    verdict=data.get("verdict", "NO TRADE"),
                    false_signal_risk=int(data.get("false_signal_risk", 0)),
                    reasons=json.dumps(data.get("reasons_reject", [])),
                )
            )
            await session.commit()

    async def all_rejections(self) -> list[RejectionRecord]:
        async with self.db.session() as session:
            result = await session.execute(select(RejectionRecord))
            return list(result.scalars().all())

    async def list_recent(self, limit: int = 20) -> list[SignalRecord]:
        async with self.db.session() as session:
            result = await session.execute(
                select(SignalRecord).order_by(SignalRecord.timestamp.desc()).limit(limit)
            )
            return list(result.scalars().all())

    async def list_open(self) -> list[SignalRecord]:
        async with self.db.session() as session:
            result = await session.execute(
                select(SignalRecord).where(SignalRecord.tracking_open == 1)
            )
            return list(result.scalars().all())

    async def set_recheck_status(self, signal_id: str, status: str) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(SignalRecord)
                .where(SignalRecord.signal_id == signal_id)
                .values(recheck_status=status, updated_at=int(time.time() * 1000))
            )
            await session.commit()

    async def invalidate(self, signal_id: str, reason: str) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(SignalRecord)
                .where(SignalRecord.signal_id == signal_id)
                .values(
                    status="INVALIDATED",
                    outcome="INVALIDATED",
                    rejection_reasons=reason[:1000],
                    tracking_open=0,
                    updated_at=int(time.time() * 1000),
                )
            )
            await session.commit()

    async def all_records(self) -> list[SignalRecord]:
        async with self.db.session() as session:
            result = await session.execute(select(SignalRecord))
            return list(result.scalars().all())

    async def count_active(self) -> int:
        return len(await self.list_open())


class PaperPositionRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def open(self, signal: Signal) -> bool:
        async with self.db.session() as session:
            existing = await session.execute(
                select(PaperPosition.id).where(PaperPosition.signal_id == signal.signal_id)
            )
            if existing.first() is not None:
                return False
            session.add(
                PaperPosition(
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    entry=signal.entry,
                    stop_loss=signal.stop_loss,
                    tp1=signal.tp1,
                    tp2=signal.tp2,
                    tp3=signal.tp3,
                    size=signal.plan.position_size,
                    notional=signal.plan.notional,
                    margin=signal.plan.margin,
                    fees=signal.plan.estimated_cost,
                    opened_at=signal.timestamp,
                )
            )
            await session.commit()
        return True

    async def list_open(self) -> list[PaperPosition]:
        async with self.db.session() as session:
            result = await session.execute(
                select(PaperPosition).where(PaperPosition.status == "OPEN")
            )
            return list(result.scalars().all())

    async def update(self, position: PaperPosition, **fields: object) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(PaperPosition).where(PaperPosition.signal_id == position.signal_id).values(**fields)
            )
            await session.commit()


class DailyReportRepository:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def upsert(self, stats: dict) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with self.db.session() as session:
            existing = await session.get(DailyReport, today)
            if existing is None:
                session.add(
                    DailyReport(
                        date=today,
                        signals=int(stats.get("total_signals", 0)),
                        wins=int(stats.get("wins", 0)),
                        losses=int(stats.get("losses", 0)),
                        pnl_usdt=float(stats.get("pnl_usdt", 0.0)),
                        max_drawdown_r=float(stats.get("max_drawdown_r", 0.0)),
                        created_at=int(time.time() * 1000),
                    )
                )
            else:
                existing.signals = int(stats.get("total_signals", 0))
                existing.wins = int(stats.get("wins", 0))
                existing.losses = int(stats.get("losses", 0))
                existing.pnl_usdt = float(stats.get("pnl_usdt", 0.0))
                existing.max_drawdown_r = float(stats.get("max_drawdown_r", 0.0))
            await session.commit()

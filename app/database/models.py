"""SQLAlchemy ORM models for signals, paper positions and daily reports."""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SignalRecord(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[int] = mapped_column(Integer, index=True)
    entry_low: Mapped[float] = mapped_column(Float)
    entry_high: Mapped[float] = mapped_column(Float)
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    rsi14: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_context: Mapped[str] = mapped_column(Text, default="")
    reasons: Mapped[str] = mapped_column(Text, default="[]")
    invalidation: Mapped[str] = mapped_column(Text, default="")
    setup_timeframe: Mapped[str] = mapped_column(String(10), default="15m")
    trigger_timeframe: Mapped[str] = mapped_column(String(10), default="5m")
    funding_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_interest: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size: Mapped[float] = mapped_column(Float, default=0.0)
    notional: Mapped[float] = mapped_column(Float, default=0.0)
    risk_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    expiration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)
    outcome: Mapped[str] = mapped_column(String(20), default="OPEN")
    realized_r: Mapped[float] = mapped_column(Float, default=0.0)
    gross_r: Mapped[float] = mapped_column(Float, default=0.0)
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    highest_tp: Mapped[int] = mapped_column(Integer, default=0)
    confirmation_score: Mapped[float] = mapped_column(Float, default=0.0)
    false_signal_risk: Mapped[int] = mapped_column(Integer, default=0)
    confirmation_status: Mapped[str] = mapped_column(String(32), default="")
    confirmation_reasons: Mapped[str] = mapped_column(Text, default="[]")
    rejection_reasons: Mapped[str] = mapped_column(Text, default="[]")
    entry_location: Mapped[str] = mapped_column(String(32), default="")
    countertrend: Mapped[bool] = mapped_column(Integer, default=0)
    market_regime: Mapped[str] = mapped_column(String(20), default="unknown")
    volatility_regime: Mapped[str] = mapped_column(String(20), default="unknown")
    recheck_status: Mapped[str] = mapped_column(String(32), default="")
    tracking_open: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[int] = mapped_column(Integer, default=0)


class RejectionRecord(Base):
    __tablename__ = "rejections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[int] = mapped_column(Integer, index=True)
    verdict: Mapped[str] = mapped_column(String(32))
    false_signal_risk: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[str] = mapped_column(Text, default="[]")


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    margin: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    opened_at: Mapped[int] = mapped_column(Integer, default=0)
    closed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    realized_r: Mapped[float] = mapped_column(Float, default=0.0)
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    tp1_hit: Mapped[bool] = mapped_column(Integer, default=0)
    tp2_hit: Mapped[bool] = mapped_column(Integer, default=0)
    tp3_hit: Mapped[bool] = mapped_column(Integer, default=0)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    signals: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    pnl_usdt: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_r: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[int] = mapped_column(Integer, default=0)

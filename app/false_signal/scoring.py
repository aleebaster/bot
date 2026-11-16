"""Confirmation Score, False Signal Risk and hard rejection rules."""

from __future__ import annotations

from app.false_signal.models import (
    BreakoutVerdict,
    CandleConfirmationResult,
    ConfirmationScore,
    EntryLocation,
    EntryQualityResult,
    EntryVerdict,
    FalseBreakoutResult,
    FalseSignalRisk,
    Finding,
    LiquidityTrapResult,
    MTFAlignment,
    MTFConfirmationResult,
    RSIConfirmationResult,
    VolumeConfirmationResult,
)


def build_confirmation_score(
    mtf: MTFConfirmationResult,
    price_action: float,
    rsi: RSIConfirmationResult,
    candle: CandleConfirmationResult,
    volume: VolumeConfirmationResult,
    breakout: FalseBreakoutResult,
    entry: EntryQualityResult,
    volatility: float,
) -> ConfirmationScore:
    from app.false_signal.false_breakout import breakout_score

    score = ConfirmationScore(
        multi_timeframe=min(20.0, mtf.score),
        price_action=max(0.0, min(15.0, price_action)),
        rsi=min(15.0, rsi.score),
        candle=min(15.0, candle.score),
        volume=min(10.0, volume.score),
        breakout=breakout_score(breakout),
        entry_location=min(10.0, entry.score),
        volatility=max(0.0, min(5.0, volatility)),
    )
    return score


def build_false_signal_risk(
    breakout: FalseBreakoutResult,
    trap: LiquidityTrapResult,
    rsi: RSIConfirmationResult,
    candle: CandleConfirmationResult,
    volume: VolumeConfirmationResult,
    mtf: MTFConfirmationResult,
    entry: EntryQualityResult,
    min_risk_reward: float,
) -> FalseSignalRisk:
    contributors: list[Finding] = []

    def add(name: str, points: int, detail: str) -> None:
        if points > 0:
            contributors.append(Finding(name, points / 100.0, detail))

    if breakout.verdict in {BreakoutVerdict.FAILED_BREAKOUT, BreakoutVerdict.STOP_HUNT_CANDIDATE}:
        add("Failed breakout", 35, breakout.detail)
    elif breakout.verdict == BreakoutVerdict.LIQUIDITY_SWEEP:
        add("Liquidity sweep", 12, breakout.detail)
    if trap.strong:
        add("Strong liquidity trap", 25, trap.detail)
    elif trap.detected:
        add("Liquidity trap evidence", 12, trap.detail)
    if rsi.divergence_warning:
        add("RSI divergence warning", 15, rsi.detail)
    if rsi.momentum_weakness:
        add("RSI momentum weakness", 8, rsi.detail)
    if not candle.direction_match:
        add("Candle direction mismatch", 12, candle.detail)
    if not candle.closed:
        add("Unclosed candle", 20, candle.detail)
    if volume.weak_participation:
        add("Weak volume participation", 12, volume.detail)
    if volume.divergence:
        add("Volume divergence", 8, volume.detail)
    if mtf.alignment == MTFAlignment.CONFLICT:
        add("Critical timeframe conflict", 20, mtf.detail)
    elif mtf.countertrend:
        add("Countertrend setup", 10, mtf.detail)
    if entry.location in {EntryLocation.LATE_ENTRY, EntryLocation.ENTRY_INVALIDATED}:
        add("Late/invalidated entry", 12, entry.detail)
    if entry.risk_reward < min_risk_reward:
        add("Insufficient RR", 10, f"RR={entry.risk_reward:.2f}")
    if entry.extension_atr > 3.0:
        add("Overextended from EMA", 8, f"{entry.extension_atr:.2f} ATR")

    return FalseSignalRisk(score=min(100, sum(int(f.strength * 100) for f in contributors)), contributors=contributors)


def hard_rejection_checks(
    breakout: FalseBreakoutResult,
    trap: LiquidityTrapResult,
    mtf: MTFConfirmationResult,
    candle: CandleConfirmationResult,
    entry: EntryQualityResult,
    fresh: bool,
    min_risk_reward: float,
) -> list[str]:
    """Return exact blocking reasons. Score never overrides these rules."""
    blocks: list[str] = []
    if breakout.failed:
        blocks.append(f"Confirmed false breakout: {breakout.detail}")
    if trap.strong:
        blocks.append(f"Strong liquidity trap ({trap.strength:.2f}): {trap.detail}")
    if mtf.alignment == MTFAlignment.CONFLICT:
        blocks.append(f"Critical higher-timeframe conflict: {mtf.detail}")
    if not candle.closed:
        blocks.append("No closed candle for confirmation")
    if not fresh:
        blocks.append("Market data is stale")
    if entry.location == EntryLocation.ENTRY_INVALIDATED:
        blocks.append(f"Entry already lost: {entry.detail}")
    if entry.risk_reward < min_risk_reward:
        blocks.append(f"Risk/Reward below minimum: {entry.risk_reward:.2f} < {min_risk_reward}")
    if entry.stop_atr_multiple > 4.0 or entry.stop_atr_multiple <= 0:
        blocks.append(f"Stop Loss not structurally valid: {entry.stop_atr_multiple:.2f}x ATR")
    return blocks


def decide_verdict(
    confirmation: ConfirmationScore,
    risk: FalseSignalRisk,
    hard_blocks: list[str],
    breakout: FalseBreakoutResult,
    trap: LiquidityTrapResult,
    entry: EntryQualityResult,
    reasons_confirm: list[str],
    reasons_reject: list[str],
) -> tuple[EntryVerdict, str]:
    if hard_blocks:
        if breakout.failed:
            return EntryVerdict.FALSE_BREAKOUT, "NO TRADE"
        if trap.strong:
            return EntryVerdict.LIQUIDITY_TRAP, "NO TRADE"
        if entry.location == EntryLocation.ENTRY_INVALIDATED:
            return EntryVerdict.INVALIDATED, "NO TRADE"
        return EntryVerdict.NO_TRADE, "NO TRADE"

    total = confirmation.total
    if total >= 90 and risk.score <= 25:
        return EntryVerdict.STRONG_ENTRY, "ENTRY CONFIRMED"
    if total >= 80 and risk.score <= 40:
        return EntryVerdict.CONFIRMED_ENTRY, "ENTRY CONFIRMED"
    if total >= 70 and risk.score <= 60:
        return EntryVerdict.EARLY_ENTRY, "WAIT FOR CONFIRMATION"
    return EntryVerdict.WEAK_SIGNAL, "NO TRADE"

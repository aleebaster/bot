"""Telegram message formatting. Every value comes from a real computed Signal."""

from __future__ import annotations

from app.false_signal.models import ConfirmationVerdict
from app.signal_engine.models import Signal


def format_signal(signal: Signal) -> str:
    plan = signal.plan
    lines = [
        "🚨 CRYPTO FUTURES SIGNAL",
        "",
        f"🪙 Symbol: {signal.symbol[:-4]}/USDT" if signal.symbol.endswith("USDT") else f"🪙 Symbol: {signal.symbol}",
        f"📊 Direction: {signal.direction}",
        f"⏱ Timeframes: {' / '.join(signal.timeframes)}",
        "",
        "🎯 ENTRY ZONE:",
        f"{plan.entry_low:.8f} – {plan.entry_high:.8f}",
        "",
        "🛑 STOP LOSS:",
        f"{plan.stop_loss:.8f}",
        "",
        "✅ TAKE PROFIT:",
        f"TP1: {plan.tp1:.8f}",
        f"TP2: {plan.tp2:.8f}",
        f"TP3: {plan.tp3:.8f}",
        "",
        f"⚖️ Risk/Reward: 1:{plan.risk_reward:.2f}",
        f"📈 Signal Score: {signal.score:.1f}/100 ({signal.score_breakdown.category})",
        f"📉 RSI 14: {signal.rsi14:.1f}" if signal.rsi14 is not None else "📉 RSI 14: n/a",
        f"📊 Trend: {signal.trend}",
    ]
    confirmation = signal.confirmation
    if confirmation:
        components = confirmation.get("confirmation_components", {})
        lines.extend(
            [
                "",
                "━━━━━━━━━━━━━━",
                "",
                "🧠 ENTRY QUALITY",
                f"Confirmation Score: {confirmation.get('confirmation_score', 0):.1f}/100 "
                f"({confirmation.get('confirmation_category', 'n/a')})",
                f"False Signal Risk: {confirmation.get('false_signal_risk', 0)}/100 "
                f"({confirmation.get('risk_category', 'n/a')})",
                "",
                f"Status: {signal.confirmation_status or confirmation.get('verdict', 'n/a')}",
            ]
        )
        check_labels = {
            "multi_timeframe": "Trend Alignment",
            "rsi": "RSI Confirmation",
            "candle": "Candlestick Confirmation",
            "volume": "Volume Confirmation",
            "breakout": "Breakout / Retest",
            "entry_location": "Entry Zone Valid",
        }
        for key, label in check_labels.items():
            value = float(components.get(key, 0))
            cap = {"multi_timeframe": 20, "rsi": 15, "candle": 15, "volume": 10, "breakout": 10, "entry_location": 10}[key]
            lines.append(f"{'✅' if value >= cap * 0.6 else '⚠️'} {label}")
        lines.extend(
            [
                "",
                "⚠️ RISK CHECK",
                f"Risk/Reward: 1:{plan.risk_reward:.2f}",
                f"Stop Distance: {plan.stop_distance:.8f}",
                f"ATR: {plan.atr:.8f}",
                f"Invalidation Level: {plan.stop_loss:.8f}",
                "",
                f"Decision: {confirmation.get('decision', 'ENTRY CONFIRMED')}",
                "",
                "━━━━━━━━━━━━━━",
            ]
        )
    lines.extend(["", "🔍 REASONS:"])
    lines.extend(f"- {reason}" for reason in signal.reasons)
    lines.extend(
        [
            "",
            "⚠️ INVALIDATION:",
            signal.invalidation,
            "",
            f"💰 Risk: {plan.risk_usdt:.2f} USDT | Size: {plan.position_size} | Margin: {plan.margin:.2f}",
            f"🧮 Est. costs: {plan.estimated_cost:.4f} USDT | ATR: {plan.atr:.8f}",
            f"🕒 Expires: {signal.expiration}",
            "",
            f"Status: {signal.status}",
            "",
            "⚠️ Analytical signal only. No real orders are placed. Paper trading mode.",
        ]
    )
    return "\n".join(lines)


def format_rejected(symbol: str, direction: str, verdict: ConfirmationVerdict) -> str:
    """Detailed rejection explanation - never a generic 'NO TRADE' only."""
    lines = [
        "⚠️ SIGNAL REJECTED",
        "",
        f"Symbol: {symbol}",
        f"Direction: {direction}",
        "",
        "Reason:",
    ]
    reasons = verdict.reasons_reject or verdict.hard_blocks
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(
        [
            "",
            f"Confirmation Score: {verdict.confirmation.total:.1f}/100 ({verdict.confirmation.category.value})",
            f"False Signal Risk: {verdict.risk.score}/100 ({verdict.risk.category.value})",
            "",
            "Decision: NO TRADE.",
        ]
    )
    return "\n".join(lines)


def format_tp_hit(signal: Signal, level: int) -> str:
    price = [signal.tp1, signal.tp2, signal.tp3][level - 1]
    return (
        f"✅ TP{level} HIT — {signal.symbol}\n"
        f"{signal.direction} | Price: {price:.8f}\n"
        f"Signal {signal.signal_id} | Consider moving SL to breakeven."
    )


def format_stop_loss(signal: Signal) -> str:
    return (
        f"🛑 STOP LOSS — {signal.symbol}\n"
        f"{signal.direction} | SL: {signal.stop_loss:.8f}\n"
        f"Signal {signal.signal_id} | Outcome: LOSS. Review the setup honestly."
    )


def format_cancellation(signal: Signal, reason: str) -> str:
    return f"❌ CANCELLED — {signal.symbol}\nSignal {signal.signal_id}\nReason: {reason}"


def format_expiry(signal: Signal) -> str:
    return (
        f"⏰ SIGNAL EXPIRED — {signal.symbol}\n"
        f"Signal {signal.signal_id} lost relevance before activation. No entry."
    )


def format_scenario_change(signal: Signal, reason: str) -> str:
    return (
        f"🔄 SCENARIO CHANGED — {signal.symbol}\n"
        f"Signal {signal.signal_id}\nReason: {reason}\nReassess before any action."
    )


def format_status(status: dict) -> str:
    lines = [
        "📊 BOT STATUS",
        f"Mode: {'PAPER TRADING' if status.get('paper_trading') else 'ANALYTICS ONLY'}",
        f"Paused: {status.get('paused')}",
        f"Active ideas: {status.get('active_ideas', 0)}/{status.get('max_concurrent_ideas', 0)}",
        f"Feed healthy: {status.get('feed_healthy')}",
        f"Watchlist: {', '.join(status.get('watchlist', []))}",
        f"Last scan: {status.get('last_scan', 'never')}",
    ]
    return "\n".join(lines)


def format_help() -> str:
    return (
        "🤖 CRYPTO FUTURES SIGNAL BOT\n\n"
        "/start — welcome\n"
        "/status — bot status\n"
        "/scan — trigger a manual scan\n"
        "/signals — recent signals\n"
        "/top — top liquid symbols\n"
        "/btc — analyse BTC\n"
        "/eth — analyse ETH\n"
        "/coin SYMBOL — analyse any symbol\n"
        "/stats — win rate, PF, expectancy\n"
        "/performance — detailed performance\n"
        "/watchlist — show watchlist\n"
        "/settings — show non-secret settings\n"
        "/help — this message\n\n"
        "Admin only: /pause, /resume, /watchlist ADD|REMOVE SYMBOL"
    )


def format_scan_summary(total: int, signals: int, no_trade: int) -> str:
    return f"🔍 Scan complete: {total} symbols | {signals} signals | {no_trade} NO TRADE (quality filter)."


def format_stats(stats: dict) -> str:
    return (
        "📈 PERFORMANCE\n"
        f"Total signals: {stats.get('total_signals', 0)}\n"
        f"Win rate: {stats.get('win_rate', 0):.1f}%\n"
        f"Loss rate: {stats.get('loss_rate', 0):.1f}%\n"
        f"Profit factor: {stats.get('profit_factor', 0):.2f}\n"
        f"Expectancy: {stats.get('expectancy_r', 0):.2f}R\n"
        f"Average R: {stats.get('average_r', 0):.2f}\n"
        f"Max drawdown: {stats.get('max_drawdown_r', 0):.2f}R"
    )

"""Telegram message formatting. Every value comes from a real computed Signal."""

from __future__ import annotations

from app.false_signal.models import ConfirmationVerdict
from app.signal_engine.models import Signal


def format_signal(signal: Signal) -> str:
    """Telegram signal. All values are computed from closed market data."""
    plan = signal.plan
    confirmation = signal.confirmation or {}
    details = confirmation.get("details", {})
    price = signal.current_price or plan.entry

    lines = [
        "🚀 CRYPTO FUTURES SIGNAL",
        "",
        f"Монета: {signal.symbol}",
        f"Напрямок: {signal.direction}",
        f"Таймфрейм: {signal.trigger_timeframe.upper()}",
        f"Поточна ціна: {price:.8f}",
        f"Зона входу: {plan.entry_low:.8f} – {plan.entry_high:.8f}",
        f"Stop Loss: {plan.stop_loss:.8f}",
        f"Take Profit 1: {plan.tp1:.8f}",
        f"Take Profit 2: {plan.tp2:.8f}",
        f"Take Profit 3: {plan.tp3:.8f}",
        "",
        "📊 ЯКІСТЬ СИГНАЛУ",
        "",
        f"Confirmation Score: {confirmation.get('confirmation_score', 0):.0f}/100",
        f"False Signal Risk: {confirmation.get('false_signal_risk', 0)}/100",
        f"Risk/Reward: 1:{plan.risk_reward:.2f}",
        "",
        "Підтвердження:",
        f"- Тренд: {details.get('trend', signal.trend)}",
        f"- EMA: {details.get('ema', 'n/a')}",
        f"- RSI: {details.get('rsi', f'RSI14={signal.rsi14}') if signal.rsi14 is not None else details.get('rsi', 'n/a')}",
        f"- VWAP: {details.get('vwap', 'n/a')}",
        f"- Volume: {details.get('volume', 'n/a')}",
        f"- Price Action: {details.get('price_action', 'n/a')}",
        f"- MTF Confirmation: {details.get('mtf', 'n/a')}",
        f"- Liquidity: {details.get('liquidity', 'n/a')}",
        "",
        "Інвалідація:",
        signal.invalidation or f"Закриття свічки нижче/вище {plan.stop_loss:.8f}",
        "",
        "Пояснення:",
    ]
    lines.extend(f"- {reason}" for reason in signal.reasons)
    lines.extend(
        [
            "",
            f"Статус: {signal.confirmation_status or confirmation.get('verdict', 'n/a')}",
            f"Рішення: {confirmation.get('decision', 'ENTRY CONFIRMED')}",
            f"ID сигналу: {signal.signal_id}",
            "",
            "⚠️ Лише аналітичний сигнал. Бот не відкриває реальні ордери.",
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
        "/status — стан системи\n"
        "/scan — запустити сканування\n"
        "/signals — останні сигнали\n"
        "/active — активні сигнали\n"
        "/stats — статистика результатів\n"
        "/market — огляд ринку\n"
        "/top — найкращі сигнали\n"
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
    lines = [
        "📈 PERFORMANCE",
        f"Total signals: {stats.get('total_signals', 0)}",
        f"Win rate: {stats.get('win_rate', 0):.1f}%",
        f"Loss rate: {stats.get('loss_rate', 0):.1f}%",
        f"Profit factor: {stats.get('profit_factor', 0):.2f}",
        f"Expectancy: {stats.get('expectancy_r', 0):.2f}R",
        f"Average R: {stats.get('average_r', 0):.2f}",
        f"Max drawdown: {stats.get('max_drawdown_r', 0):.2f}R",
        f"Rejected ideas: {stats.get('total_rejections', 0)}",
        f"False breakout rate: {stats.get('false_breakout_rate', 0):.1f}%",
        f"Liquidity trap rate: {stats.get('liquidity_trap_rate', 0):.1f}%",
        f"TP1 / TP2 / TP3: {stats.get('tp1_rate', 0):.1f}% / {stats.get('tp2_rate', 0):.1f}% / {stats.get('tp3_rate', 0):.1f}%",
        f"SL rate: {stats.get('sl_rate', 0):.1f}%",
        f"Average RR: 1:{stats.get('average_risk_reward', 0):.2f}",
        f"LONG / SHORT: {stats.get('by_direction', {}).get('LONG', {}).get('signals', 0)} / "
        f"{stats.get('by_direction', {}).get('SHORT', {}).get('signals', 0)}",
        "By entry status:",
    ]
    for status, data in (stats.get("by_confirmation_status") or {}).items():
        lines.append(
            f"  {status}: {data.get('signals', 0)} signals, WR {data.get('win_rate', 0):.1f}%, "
            f"expectancy {data.get('expectancy_r', 0):.2f}R"
        )
    lines.append("")
    lines.append("⚠️ Симуляція на закритих свічках: комісії, slippage та funding враховані. Реального виконання немає.")
    return "\n".join(lines)

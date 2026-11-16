"""aiogram 3.x bot with public info commands and admin-only controls."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.config import Settings
from app.signal_engine.models import EngineResult
from app.telegram_bot.formatter import (
    format_help,
    format_scan_summary,
    format_signal,
    format_stats,
    format_status,
)
from app.telegram_bot.notifier import TelegramNotifier

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = {"pause", "resume"}


@dataclass
class BotContext:
    """Injected services used by command handlers."""

    settings: Settings
    notifier: TelegramNotifier
    get_status: Callable[[], dict] = field(default=lambda: {})
    request_scan: Callable[[], None] = field(default=lambda: None)
    analyze_symbol: Callable[[str], EngineResult] = field(
        default=lambda symbol: EngineResult(None, "Analysis service unavailable")
    )
    recent_signals: Callable[[], list[dict]] = field(default=list)
    get_stats: Callable[[], dict] = field(default=dict)
    get_top_symbols: Callable[[], list[str]] = field(default=list)
    set_watchlist: Callable[[list[str]], None] = field(default=lambda symbols: None)
    paused: bool = False


async def _resolve(value):
    """Accept sync or async service callables in handlers."""
    return await value if inspect.isawaitable(value) else value


def create_dispatcher(context: BotContext) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    def is_admin(message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in context.settings.admin_telegram_ids

    @dp.message(Command("start", "help"))
    async def help_handler(message: Message) -> None:
        await message.answer("👋 Welcome to CRYPTO FUTURES SIGNAL BOT\n\n" + format_help())

    @dp.message(Command("status"))
    async def status_handler(message: Message) -> None:
        status = await _resolve(context.get_status())
        status["paused"] = context.paused
        status["paper_trading"] = context.settings.paper_trading
        status["max_concurrent_ideas"] = context.settings.max_concurrent_ideas
        await message.answer(format_status(status))

    @dp.message(Command("scan"))
    async def scan_handler(message: Message) -> None:
        context.request_scan()
        await message.answer("🔍 Scan requested. Results will arrive as they are generated.")

    @dp.message(Command("signals"))
    async def signals_handler(message: Message) -> None:
        recent = await _resolve(context.recent_signals())
        if not recent:
            await message.answer("No signals recorded yet.")
            return
        lines = ["📋 RECENT SIGNALS"]
        for item in recent[-10:]:
            lines.append(
                f"{item.get('symbol', '?')} {item.get('direction', '?')} "
                f"score={item.get('score', 0)} | {item.get('status', '?')}"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("top"))
    async def top_handler(message: Message) -> None:
        symbols = await _resolve(context.get_top_symbols())
        await message.answer("🏆 Top liquid symbols:\n" + (", ".join(symbols) if symbols else "unavailable"))

    @dp.message(Command("btc", "eth"))
    async def quick_coin_handler(message: Message) -> None:
        symbol = "BTCUSDT" if message.text and "/btc" in message.text.lower() else "ETHUSDT"
        result = await _resolve(context.analyze_symbol(symbol))
        await _send_analysis(message, symbol, result)

    @dp.message(Command("coin"))
    async def coin_handler(message: Message, command: CommandObject) -> None:
        raw = (command.args or "").strip().upper()
        if not raw:
            await message.answer("Usage: /coin BTCUSDT")
            return
        symbol = raw if raw.endswith("USDT") else f"{raw}USDT"
        await _send_analysis(message, symbol, await _resolve(context.analyze_symbol(symbol)))

    @dp.message(Command("stats", "performance"))
    async def stats_handler(message: Message) -> None:
        await message.answer(format_stats(await _resolve(context.get_stats())))

    @dp.message(Command("watchlist"))
    async def watchlist_handler(message: Message, command: CommandObject) -> None:
        args = (command.args or "").strip()
        if not args:
            await message.answer("Watchlist:\n" + ", ".join(context.settings.watchlist))
            return
        if not is_admin(message):
            await message.answer("⛔ Changing the watchlist is restricted to authorised users.")
            return
        parts = args.split()
        if len(parts) != 2 or parts[0].upper() not in {"ADD", "REMOVE"}:
            await message.answer("Usage: /watchlist ADD BTCUSDT | /watchlist REMOVE BTCUSDT")
            return
        action, symbol = parts[0].upper(), parts[1].upper()
        current = list(context.settings.watchlist)
        if action == "ADD" and symbol not in current:
            current.append(symbol)
        elif action == "REMOVE" and symbol in current:
            current.remove(symbol)
        context.set_watchlist(current)
        context.settings.watchlist = current
        await message.answer(f"Watchlist updated ({len(current)} symbols).")

    @dp.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        s = context.settings
        await message.answer(
            "⚙️ Settings (non-secret)\n"
            f"Risk/trade: {s.risk_per_trade:.2%}\n"
            f"Leverage: {s.leverage}x\n"
            f"Min RR: {s.min_risk_reward}\n"
            f"Min score: {s.min_signal_score}\n"
            f"Paper trading: {s.paper_trading}\n"
            f"Scan interval: {s.scan_interval_seconds}s"
        )

    @dp.message(Command("pause", "resume"))
    async def pause_handler(message: Message) -> None:
        if not is_admin(message):
            await message.answer("⛔ Admin command restricted to authorised users.")
            return
        command_name = (message.text or "").split()[0].lstrip("/").lower()
        context.paused = command_name == "pause"
        await message.answer(f"Signal generation {'PAUSED' if context.paused else 'RESUMED'}.")

    return dp


async def _send_analysis(message: Message, symbol: str, result: EngineResult) -> None:
    if result.signal is not None:
        await message.answer(format_signal(result.signal))
    else:
        await message.answer(f"⏸ NO TRADE — {symbol}\nReason: {result.reason}")


async def run_bot(settings: Settings, notifier: TelegramNotifier, context: BotContext) -> None:
    """Start long-polling. Requires a configured bot token."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set - Telegram bot disabled")
        return
    bot = Bot(token=settings.telegram_bot_token)
    notifier.bot = bot
    dispatcher = create_dispatcher(context)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()

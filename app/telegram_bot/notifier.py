"""Outbound Telegram notifier with duplicate-message suppression."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.config import Settings
from app.signal_engine.models import Signal
from app.false_signal.models import ConfirmationVerdict
from app.telegram_bot.formatter import (
    format_cancellation,
    format_expiry,
    format_rejected,
    format_scenario_change,
    format_signal,
    format_stop_loss,
    format_tp_hit,
)

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends notifications and prevents duplicate sends for the same event.

    If no bot/chat is configured, messages are logged and dropped: the engine
    remains fully functional in offline/analytics mode and tests never need
    real credentials.
    """

    def __init__(self, settings: Settings, bot: Bot | None = None) -> None:
        self.settings = settings
        self.bot = bot
        self._seen: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self.bot is not None and bool(self.settings.telegram_chat_id)

    async def send(self, text: str, dedup_key: str | None = None) -> bool:
        """Send a message. Returns True only if it was actually delivered."""
        if dedup_key:
            async with self._lock:
                if dedup_key in self._seen:
                    logger.debug("Duplicate notification suppressed: %s", dedup_key)
                    return False
                if len(self._seen) > 10_000:
                    self._seen.clear()
                self._seen.add(dedup_key)
        if not self.configured:
            logger.info("Telegram not configured; message not sent (dry run)")
            return False
        for attempt in range(1, 4):
            try:
                await self.bot.send_message(chat_id=self.settings.telegram_chat_id, text=text)
                return True
            except Exception as exc:
                if attempt == 3:
                    logger.error("Telegram send failed after 3 attempts: %s", type(exc).__name__)
                    return False
                delay = 0.5 * (2 ** (attempt - 1))
                logger.warning("Telegram send attempt %d failed (%s), retry in %.1fs", attempt, type(exc).__name__, delay)
                await asyncio.sleep(delay)
        return False

    async def send_signal(self, signal: Signal) -> bool:
        return await self.send(format_signal(signal), dedup_key=f"signal:{signal.signal_id}")

    async def rejected(self, symbol: str, direction: str, verdict: ConfirmationVerdict) -> bool:
        """Send a detailed rejection note once per identical reason."""
        reason_key = "|".join(verdict.reasons_reject or verdict.hard_blocks)
        return await self.send(
            format_rejected(symbol, direction, verdict),
            dedup_key=f"rejected:{symbol}:{direction}:{reason_key}",
        )

    async def tp_hit(self, signal: Signal, level: int) -> bool:
        return await self.send(format_tp_hit(signal, level), dedup_key=f"tp{level}:{signal.signal_id}")

    async def stop_loss(self, signal: Signal) -> bool:
        return await self.send(format_stop_loss(signal), dedup_key=f"sl:{signal.signal_id}")

    async def cancelled(self, signal: Signal, reason: str) -> bool:
        return await self.send(format_cancellation(signal, reason), dedup_key=f"cancel:{signal.signal_id}")

    async def expired(self, signal: Signal) -> bool:
        return await self.send(format_expiry(signal), dedup_key=f"expired:{signal.signal_id}")

    async def scenario_changed(self, signal: Signal, reason: str) -> bool:
        return await self.send(
            format_scenario_change(signal, reason), dedup_key=f"scenario:{signal.signal_id}:{reason}"
        )

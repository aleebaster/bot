"""Proposed V6 Telegram messages for SIGNAL-ONLY observation mode.

Isolated experimental design: these functions are NOT wired into production.
All prices are derived from real computed rows; no demo values are used.
"""

from __future__ import annotations

from app.constants import LONG


def _risk(row: dict) -> float:
    return abs(row["entry"] - row["stop_loss"])


def _original_zone(row: dict) -> tuple[float, float]:
    # Entry zone used by the production engine: 5M close +/- 0.15 * ATR(5M).
    # The recorded structural risk equals ~1.5 x ATR in the trade plan.
    atr = _risk(row) / 1.5
    return row["entry"] - 0.15 * atr, row["entry"] + 0.15 * atr


def _new_plan(row: dict) -> tuple[float, float, float, float]:
    sign = 1 if row["direction"] == LONG else -1
    entry = row.get("next_bar_entry", row["entry"])
    risk = _risk(row)
    return entry, entry - sign * risk, entry + sign * risk, entry + sign * 3 * risk


def format_early_signal(row: dict) -> str:
    low, high = _original_zone(row)
    return "\n".join([
        "EARLY SIGNAL DETECTED",
        "",
        f"Монета: {row['symbol']}",
        f"Напрямок: {row['direction']}",
        f"Початкова зона входу: {low:.8f} – {high:.8f}",
        f"Поточна ціна: {row['close']:.8f}",
        "Статус: WAITING FOR CONFIRMATION",
        "",
        f"ID: {row.get('signal_id', 'n/a')}",
        f"Confirmation Score: {row['confirmation_score']:.0f}/100",
        f"False Signal Risk: {row['false_signal_risk']}/100",
        "",
        "⚠️ Очікуємо закриття наступної свічки. Сигнал ще не підтверджено.",
    ])


def format_confirmed_entry(row: dict) -> str:
    entry, stop, tp1, tp3 = _new_plan(row)
    sign = 1 if row["direction"] == LONG else -1
    risk = _risk(row)
    tp2 = entry + sign * 2 * risk
    return "\n".join([
        "CONFIRMED ENTRY",
        "",
        f"Монета: {row['symbol']}",
        f"Напрямок: {row['direction']}",
        f"Нова зона входу: {entry:.8f}",
        f"Stop Loss: {stop:.8f}",
        f"Take Profit 1: {tp1:.8f}",
        f"Take Profit 2: {tp2:.8f}",
        f"Take Profit 3: {tp3:.8f}",
        f"Confirmation Score: {row.get('next_bar_score', row['confirmation_score']):.0f}/100",
        f"False Signal Risk: {row.get('next_bar_risk', row['false_signal_risk'])}/100",
        "",
        f"Зсув входу: {row.get('entry_shift_atr', 0):.3f} ATR",
        "⚠️ Лише спостереження. Бот не відкриває ордери.",
    ])


def format_invalidated(row: dict) -> str:
    return "\n".join([
        "SIGNAL INVALIDATED",
        "",
        f"Монета: {row['symbol']}",
        f"Напрямок: {row['direction']}",
        f"Причина відхилення: {row.get('reason', 'next bar did not confirm')}",
        "",
        "⚠️ Скасовано до входу. Реального виконання не було.",
    ])


def format_expired(row: dict) -> str:
    return "\n".join([
        "SIGNAL EXPIRED",
        "",
        f"Монета: {row['symbol']}",
        f"Напрямок: {row['direction']}",
        f"Причина: {row.get('reason', 'entry zone no longer valid')}",
        "",
        "⚠️ Вхід утратив актуальність. Реального виконання не було.",
    ])

# V6 Signal-Only Design (isolated experiment)

This design is **not merged into production**. Production keeps SIGNAL_ONLY=true, PAPER_TRADING=false, the 80/100 threshold and all current weights.

## Status flow

1. EARLY signal detected → Telegram: `EARLY SIGNAL DETECTED` with original entry zone, current price and `WAITING FOR CONFIRMATION`.
2. Next 5M candle closes → the same filter is re-run on past-only data.
3. Confirmed AND price still inside the valid entry zone → `CONFIRMED ENTRY` with the NEW entry zone, SL, TP1/TP2/TP3, new scores and actual entry shift.
4. Not confirmed → `SIGNAL INVALIDATED` with the exact rejection reason.
5. Price already beyond the allowed zone → `SIGNAL EXPIRED` with the reason.

No confirmed signal is sent if the entry is stale. No message is sent on every price tick.

## Message templates (values from computed rows)

```text
EARLY SIGNAL DETECTED
Монета: ...
Напрямок: ...
Початкова зона входу: ...
Поточна ціна: ...
Статус: WAITING FOR CONFIRMATION

CONFIRMED ENTRY
Нова зона входу: ...
Stop Loss: ...
Take Profit 1/2/3: ...
Confirmation Score: ...
False Signal Risk: ...

SIGNAL INVALIDATED / SIGNAL EXPIRED + причина
```

## Safety

- Isolated module `experiments/v6/telegram_design.py`; never imported by `app/`.
- No exchange order calls; no API keys; no real positions.
- Automated guard test scans for trading API usage in the whole repository.

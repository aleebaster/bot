"""Shared constants for the CRYPTO FUTURES SIGNAL BOT."""

from __future__ import annotations

# Ordered from highest to lowest timeframe. Multi-timeframe analysis walks this
# list top-down: higher timeframes provide context, lower timeframes provide
# the setup and the trigger.
TIMEFRAMES: tuple[str, ...] = ("1d", "4h", "1h", "15m", "5m")

CONTEXT_TIMEFRAME = "1d"
TREND_TIMEFRAME = "4h"
CONFIRM_TIMEFRAME = "1h"
SETUP_TIMEFRAME = "15m"
TRIGGER_TIMEFRAME = "5m"

DEFAULT_WATCHLIST: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "NEARUSDT",
    "SUIUSDT",
    "LTCUSDT",
)

# Signal score thresholds.
SCORE_EXCELLENT = 90
SCORE_STRONG = 80
SCORE_MODERATE = 70

# Canonical long/short labels.
LONG = "LONG"
SHORT = "SHORT"
NO_TRADE = "NO TRADE"

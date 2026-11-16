"""Exchange client for Binance USD-M futures public market data (via ccxt)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import ccxt.async_support as ccxt

from app.config import Settings
from app.market_data.models import Candle, timeframe_to_ms

logger = logging.getLogger(__name__)

LEVERAGED_SUFFIXES = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


class ExchangeClient:
    """Async wrapper around ccxt with retry, time-sync and symbol helpers.

    Only public endpoints are used. Credentials, when provided, are passed
    through to ccxt but no trading endpoint is ever called.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.exchange: Any | None = None
        self._time_offset_ms = 0

    async def connect(self) -> None:
        exchange_class = getattr(ccxt, self.settings.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange: {self.settings.exchange_id!r}")

        options: dict[str, Any] = {"enableRateLimit": self.settings.enable_rate_limit}
        if self.settings.futures:
            options["options"] = {"defaultType": "swap"}

        self.exchange = exchange_class(options)
        if self.settings.binance_api_key and self.settings.binance_api_secret:
            # Optional: public data works without keys; no trading is performed.
            self.exchange.apiKey = self.settings.binance_api_key
            self.exchange.secret = self.settings.binance_api_secret

        await self.exchange.load_markets()
        try:
            server_time = await self.exchange.fetch_time()
            self._time_offset_ms = int(server_time) - int(time.time() * 1000)
            logger.info("Exchange time sync offset: %d ms", self._time_offset_ms)
        except Exception as exc:  # pragma: no cover - depends on exchange availability
            logger.warning("Time sync failed, using local clock: %s", exc)

    @property
    def now_ms(self) -> int:
        """Server-synchronised current time in milliseconds."""
        return int(time.time() * 1000) + self._time_offset_ms

    def ccxt_symbol(self, symbol: str) -> str:
        """Convert a unified symbol (BTCUSDT) to a ccxt futures symbol."""
        sym = symbol.upper().replace("_", "")
        if ":" in sym or "/" in sym:
            return sym
        if self.settings.futures:
            return f"{sym[:-4]}/USDT:USDT" if sym.endswith("USDT") else f"{sym}/USDT:USDT"
        return f"{sym[:-4]}/USDT" if sym.endswith("USDT") else f"{sym}/USDT"

    def display_symbol(self, symbol: str) -> str:
        """Convert to a display form such as BTC/USDT."""
        base = self.ccxt_symbol(symbol).split(":")[0].replace("/", "")
        return f"{base[:-4]}/USDT" if base.endswith("USDT") else base

    async def _retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        attempts: int = 3,
        base_delay: float = 1.0,
        **kwargs: Any,
    ) -> Any:
        """Retry transient network/rate-limit failures with exponential backoff."""
        for attempt in range(1, attempts + 1):
            try:
                return await func(*args, **kwargs)
            except (
                ccxt.NetworkError,
                ccxt.RateLimitExceeded,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
            ) as exc:
                if attempt >= attempts:
                    logger.error("Exchange call failed after %d attempts: %s", attempts, exc)
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning("Exchange call error (attempt %d/%d): %s - retry in %.1fs", attempt, attempts, exc, delay)
                await asyncio.sleep(delay)

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int | None = None, since: int | None = None
    ) -> list[Candle]:
        """Fetch OHLCV bars and flag the still-forming bar as not closed."""
        limit = limit or self.settings.ohlcv_limit
        rows = await self._retry(
            self.exchange.fetch_ohlcv,
            self.ccxt_symbol(symbol),
            timeframe,
            limit,
            since,
        )
        step = timeframe_to_ms(timeframe)
        now = self.now_ms
        candles: list[Candle] = []
        for row in rows:
            ts = int(row[0])
            o, h, l, c, v = map(float, row[1:6])
            candles.append(Candle(ts, o, h, l, c, v, closed=(ts + step <= now)))
        return candles

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return await self._retry(self.exchange.fetch_ticker, self.ccxt_symbol(symbol))

    async def fetch_funding_rate(self, symbol: str) -> float | None:
        """Current funding rate as a decimal (e.g. 0.0001 = 0.01%)."""
        try:
            data = await self._retry(self.exchange.fetch_funding_rate, self.ccxt_symbol(symbol))
            value = data.get("fundingRate")
            return float(value) if value is not None else None
        except Exception as exc:
            logger.debug("Funding rate unavailable for %s: %s", symbol, exc)
            return None

    async def fetch_open_interest(self, symbol: str) -> float | None:
        """Open interest in base units, if the endpoint is available."""
        try:
            data = await self._retry(self.exchange.fetch_open_interest, self.ccxt_symbol(symbol))
            value = data.get("openInterestAmount") or data.get("openInterest")
            return float(value) if value is not None else None
        except Exception as exc:
            logger.debug("Open interest unavailable for %s: %s", symbol, exc)
            return None

    async def get_top_liquid_symbols(self, limit: int | None = None) -> list[str]:
        """Auto-scanner: top USDT-M contracts by 24h quote volume."""
        limit = limit or self.settings.top_n_scanner
        try:
            tickers = await self._retry(self.exchange.fetch_tickers)
        except Exception as exc:
            logger.warning("Auto scanner could not fetch tickers: %s", exc)
            return []

        candidates: list[tuple[float, str]] = []
        for market_symbol, ticker in tickers.items():
            if not market_symbol.endswith(":USDT"):
                continue
            quote_volume = ticker.get("quoteVolume") or 0.0
            if quote_volume < self.settings.min_volume_usdt:
                continue
            base = market_symbol.split(":")[0].split("/")[0]
            if any(base.endswith(sfx) for sfx in LEVERAGED_SUFFIXES):
                continue
            market = (self.exchange.markets or {}).get(market_symbol, {})
            if market.get("active") is False:
                continue
            candidates.append((float(quote_volume), f"{base}USDT"))

        candidates.sort(reverse=True)
        return [symbol for _, symbol in candidates[:limit]]

    async def close(self) -> None:
        if self.exchange is not None:
            await self.exchange.close()
            self.exchange = None

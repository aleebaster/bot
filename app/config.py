"""Central configuration loaded from environment variables / .env.

Secrets are never hard-coded here. All credentials come from the environment,
and ``.env`` is git-ignored. See ``.env.example`` for the full list of keys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from app.constants import DEFAULT_WATCHLIST

load_dotenv()


def _csv_ints(value: str | None) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            try:
                out.append(int(part))
            except ValueError:
                continue
    return out


def _csv_strs(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip().upper() for p in value.split(",") if p.strip()]


class Settings(BaseModel):
    """Application settings with safe defaults for analysis / paper trading."""

    # --- Telegram -----------------------------------------------------------
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    admin_telegram_ids: list[int] = Field(default_factory=list)

    # --- Exchange (public market data does not require credentials) ---------
    exchange_id: str = "binance"
    binance_api_key: str = ""
    binance_api_secret: str = ""
    futures: bool = True
    enable_rate_limit: bool = True

    # --- Risk ---------------------------------------------------------------
    account_balance: float = 1000.0
    risk_per_trade: float = 0.005  # 0.5%
    leverage: float = 1.0
    max_concurrent_ideas: int = 3
    min_risk_reward: float = 2.0
    min_signal_score: int = 80

    # --- Cost model ---------------------------------------------------------
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    slippage: float = 0.0005
    funding_per_8h: float = 0.0001
    max_holding_bars_for_funding: int = 24

    # --- Market data --------------------------------------------------------
    ohlcv_limit: int = 400
    min_volume_usdt: float = 5_000_000.0
    max_quote_age_seconds: int = 180
    scan_interval_seconds: int = 60
    ws_enabled: bool = True
    top_n_scanner: int = 20

    # --- Storage / runtime --------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/signals.db"
    log_level: str = "INFO"
    paper_trading: bool = True  # default mode; real orders are never placed
    dry_run: bool = True
    watchlist: list[str] = Field(default_factory=lambda: list(DEFAULT_WATCHLIST))

    # --- Validators ---------------------------------------------------------
    @field_validator("risk_per_trade")
    @classmethod
    def _risk_bounds(cls, v: float) -> float:
        if not 0.0 < v <= 0.05:
            raise ValueError("risk_per_trade must be in (0, 0.05]")
        return v

    @field_validator("leverage", "min_risk_reward")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("value must be positive")
        return v

    @field_validator("min_signal_score")
    @classmethod
    def _score_bounds(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("min_signal_score must be in [0, 100]")
        return v

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the process environment / loaded .env file."""
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            admin_telegram_ids=_csv_ints(os.getenv("ADMIN_TELEGRAM_IDS")),
            exchange_id=os.getenv("EXCHANGE_ID", "binance"),
            binance_api_key=os.getenv("BINANCE_API_KEY", ""),
            binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
            futures=os.getenv("FUTURES", "true").lower() in {"1", "true", "yes"},
            enable_rate_limit=os.getenv("ENABLE_RATE_LIMIT", "true").lower()
            in {"1", "true", "yes"},
            account_balance=float(os.getenv("ACCOUNT_BALANCE", "1000")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.005")),
            leverage=float(os.getenv("LEVERAGE", "1")),
            max_concurrent_ideas=int(os.getenv("MAX_CONCURRENT_IDEAS", "3")),
            min_risk_reward=float(os.getenv("MIN_RISK_REWARD", "2.0")),
            min_signal_score=int(os.getenv("MIN_SIGNAL_SCORE", "80")),
            taker_fee=float(os.getenv("TAKER_FEE", "0.0004")),
            maker_fee=float(os.getenv("MAKER_FEE", "0.0002")),
            slippage=float(os.getenv("SLIPPAGE", "0.0005")),
            funding_per_8h=float(os.getenv("FUNDING_PER_8H", "0.0001")),
            max_holding_bars_for_funding=int(os.getenv("MAX_HOLDING_BARS_FUNDING", "24")),
            ohlcv_limit=int(os.getenv("OHLCV_LIMIT", "400")),
            min_volume_usdt=float(os.getenv("MIN_VOLUME_USDT", "5000000")),
            max_quote_age_seconds=int(os.getenv("MAX_QUOTE_AGE_SECONDS", "180")),
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "60")),
            ws_enabled=os.getenv("WS_ENABLED", "true").lower() in {"1", "true", "yes"},
            top_n_scanner=int(os.getenv("TOP_N_SCANNER", "20")),
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/signals.db"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            paper_trading=os.getenv("PAPER_TRADING", "true").lower()
            in {"1", "true", "yes"},
            dry_run=os.getenv("DRY_RUN", "true").lower() in {"1", "true", "yes"},
            watchlist=_csv_strs(os.getenv("WATCHLIST")) or list(DEFAULT_WATCHLIST),
        )

    @property
    def data_dir(self) -> Path:
        return Path("data")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (call ``get_settings.cache_clear()`` in tests)."""
    return Settings.from_env()

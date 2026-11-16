"""Async database lifecycle management (SQLite via aiosqlite)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite"):
            Path("data").mkdir(exist_ok=True)
        self.engine = create_async_engine(url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Database initialised")

    def session(self) -> AsyncSession:
        return self.session_factory()

    async def close(self) -> None:
        await self.engine.dispose()

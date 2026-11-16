"""Async database lifecycle management (SQLite via aiosqlite)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base, PaperPosition, RejectionRecord, SignalRecord

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
            await connection.run_sync(self._migrate_sqlite)
        logger.info("Database initialised")

    @staticmethod
    def _migrate_sqlite(connection) -> None:
        """Add new columns to an existing SQLite DB (idempotent, no data loss)."""
        if connection.dialect.name != "sqlite":
            return
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        for model in (SignalRecord, PaperPosition, RejectionRecord):
            table_name = model.__tablename__
            if table_name not in existing_tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column in model.__table__.columns:
                if column.name in columns:
                    continue
                column_type = str(column.type.compile(connection.dialect))
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}")
                )
                logger.info("Migrated %s: added column %s", table_name, column.name)

    def session(self) -> AsyncSession:
        return self.session_factory()

    async def close(self) -> None:
        await self.engine.dispose()

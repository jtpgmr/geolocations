from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

from pydantic import PostgresDsn
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseConnectError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AsyncDatabase.connect() not called")


class DatabaseTransactionError(RuntimeError):
    pass


class Database:
    """Owns one async engine + pool. Cheap to construct; `connect()` builds
    the pool, `close()` disposes it. Use as an async context manager."""

    def __init__(
        self,
        dsn: str | PostgresDsn,
        *,
        pool_size: int = 10,
        max_overflow: int = 10,
        echo: bool = False,
    ) -> None:
        self._dsn = str(dsn)
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._echo = echo
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def connect(self) -> None:
        if self._engine is not None:
            return

        engine = create_async_engine(
            self._dsn,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            pool_pre_ping=True,  # detect stale/killed connections
            pool_recycle=1800,  # beat idle-timeout (managed Postgres often ~30min)
            echo=self._echo,
        )

        self._engine = engine
        self._sessionmaker = async_sessionmaker(
            self._engine, expire_on_commit=False, autoflush=False
        )

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    async def __aenter__(self) -> Self:
        self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise DatabaseConnectError()
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise DatabaseConnectError()

        async with self._sessionmaker() as session:
            yield session

    @asynccontextmanager
    async def transaction(
        self, read_only: bool | None = True
    ) -> AsyncIterator[AsyncSession]:
        async with self.session() as session, session.begin():
            try:
                if read_only:
                    await session.execute(
                        text("SET TRANSACTION READ ONLY")
                    )  # must be first
                    await session.execute(
                        text("SELECT set_config('statement_timeout', :timeout, true)"),
                        {"timeout": "10s"},
                    )

                yield session

            except SQLAlchemyError as exc:
                # session.begin() has already rolled back here.
                raise DatabaseTransactionError("Database transaction failed") from exc

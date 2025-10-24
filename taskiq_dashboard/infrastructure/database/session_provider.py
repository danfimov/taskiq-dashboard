import typing as tp
import uuid
from contextlib import asynccontextmanager

from sqlalchemy.ext import asyncio as sa_async

from taskiq_dashboard.infrastructure.settings import PostgresSettings


class AsyncPostgresSessionProvider:
    def __init__(
        self,
        connection_settings: PostgresSettings,
    ) -> None:
        self._engine = sa_async.create_async_engine(
            connection_settings.dsn.get_secret_value(),
            echo=False,
            pool_size=connection_settings.min_pool_size,
            max_overflow=connection_settings.max_pool_size - connection_settings.min_pool_size,
            execution_options={'prepare': False},
            connect_args={  # for connection through pgbouncer
                'statement_cache_size': 0,
                'prepared_statement_cache_size': 0,
                'prepared_statement_name_func': lambda: f'__asyncpg_{uuid.uuid4()}__',
            },
        )
        self._session_factory = sa_async.async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=sa_async.AsyncSession,
        )

    @asynccontextmanager
    async def session(self) -> tp.AsyncGenerator[sa_async.AsyncSession, None]:
        """
        Create and manage a new AsyncSession.

        Usage:
            async with repository.session() as session:
                # use session for database operations
                result = await session.execute(...)
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Close the engine and release all connections."""
        await self._engine.dispose()

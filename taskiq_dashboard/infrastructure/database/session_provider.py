import typing as tp
import uuid
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.ext import asyncio as sa_async

from taskiq_dashboard.infrastructure import PostgresSettings, SqliteSettings


class AsyncPostgresSessionProvider:
    def __init__(
        self,
        connection_settings: PostgresSettings | SqliteSettings,
        engine_parameters: dict[str, tp.Any] | None = None,
    ) -> None:
        default_engine_parameters: dict[str, tp.Any] = {
            'echo': False,
        }
        self.has_index_management_connection = (
            isinstance(connection_settings, PostgresSettings) and connection_settings.index_management_dsn is not None
        )
        self._index_management_dsn = (
            connection_settings.index_management_dsn if isinstance(connection_settings, PostgresSettings) else None
        )

        if isinstance(connection_settings, PostgresSettings):
            default_engine_parameters.update(
                {
                    'pool_size': connection_settings.min_pool_size,
                    'max_overflow': connection_settings.max_pool_size - connection_settings.min_pool_size,
                }
            )
            if 'asyncpg' in connection_settings.driver:
                default_engine_parameters.update(
                    {
                        'execution_options': {'prepare': False},
                        'connect_args': {  # for connection through pgbouncer
                            'statement_cache_size': 0,
                            'prepared_statement_cache_size': 0,
                            'prepared_statement_name_func': lambda: f'__asyncpg_{uuid.uuid4()}__',
                        },
                    }
                )
            self.storage_type = 'postgres'
        else:
            self.storage_type = 'sqlite'

        self._engine_parameters = default_engine_parameters | (engine_parameters or {})
        self._engine = sa_async.create_async_engine(
            connection_settings.dsn.get_secret_value(),
            **self._engine_parameters,
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

    @asynccontextmanager
    async def autocommit_connection(self) -> tp.AsyncGenerator[sa_async.AsyncConnection, None]:
        """Open a dedicated connection for DDL that cannot run in a transaction."""
        async with self._engine.connect() as connection:
            yield await connection.execution_options(isolation_level='AUTOCOMMIT')

    @asynccontextmanager
    async def index_management_connection(self) -> tp.AsyncGenerator[sa_async.AsyncConnection, None]:
        """Use the explicit session-scoped DDL endpoint and close its connection after use."""
        if self._index_management_dsn is None:
            raise ValueError('A direct or session-pooled index_management_dsn is required for index DDL')
        # A separate, unpooled connection keeps advisory locks out of the application's pool.
        parameters = {
            key: value
            for key, value in self._engine_parameters.items()
            if key not in {'pool', 'poolclass', 'max_overflow', 'creator', 'async_creator'}
            and not key.startswith('pool_')
        }
        parameters['connect_args'] = {
            key: value
            for key, value in parameters.get('connect_args', {}).items()
            if key
            not in {'dsn', 'host', 'hostaddr', 'port', 'database', 'dbname', 'user', 'password', 'async_creator_fn'}
        }
        parameters['poolclass'] = sa.pool.NullPool
        engine = sa_async.create_async_engine(self._index_management_dsn.get_secret_value(), **parameters)
        try:
            async with engine.connect() as connection:
                yield await connection.execution_options(isolation_level='AUTOCOMMIT')
        finally:
            await engine.dispose()

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress

import pytest
from sqlalchemy.ext import asyncio as sa_async
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy_utils import create_database, database_exists, drop_database

from tests.integration.factories import PostgresTaskFactory

from taskiq_dashboard.domain.repositories import AbstractTaskRepository
from taskiq_dashboard.infrastructure import get_settings
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.repositories import TaskRepository
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.settings import PostgresSettings


class _TransactionalSessionProvider(AsyncPostgresSessionProvider):
    """Test-only variant bound to a connection with an already-open transaction."""

    def __init__(self, connection: sa_async.AsyncConnection, storage_type: str) -> None:
        self.storage_type = storage_type
        self._session_factory = sa_async.async_sessionmaker(
            bind=connection,
            join_transaction_mode='create_savepoint',
            expire_on_commit=False,
            class_=sa_async.AsyncSession,
        )


@pytest.fixture(scope='session')
def postgres() -> Generator[PostgresSettings]:
    """
    Creates a temporary database for tests
    """
    settings = get_settings()

    tmp_name = f'{uuid.uuid4().hex}.pytest'
    settings.postgres.database = tmp_name
    os.environ['POSTGRES__DATABASE'] = tmp_name
    settings.postgres.driver = 'postgresql+psycopg'
    tmp_url = settings.postgres.dsn.get_secret_value()
    settings.postgres.driver = 'postgresql+asyncpg'

    if not database_exists(tmp_url):
        create_database(tmp_url)
    try:
        yield settings.postgres
    finally:
        with suppress(Exception):
            drop_database(tmp_url)


@pytest.fixture(scope='session')
def _schema_ready(postgres: PostgresSettings) -> None:
    """Create the schema once per test session."""

    async def _create_schema() -> None:
        provider = AsyncPostgresSessionProvider(connection_settings=postgres)
        try:
            await SchemaService(provider).create_schema()
        finally:
            await provider.close()

    asyncio.run(_create_schema())


@pytest.fixture
def database(postgres: PostgresSettings, _schema_ready: None) -> PostgresSettings:
    """Settings pointing at a temp database whose schema is ready to use."""
    return postgres


@pytest.fixture
async def db_connection(postgres: PostgresSettings, _schema_ready: None) -> AsyncGenerator[AsyncConnection]:
    """A single connection with an open transaction, rolled back after the test."""
    engine = create_async_engine(postgres.dsn.get_secret_value())
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
def session_provider(db_connection: AsyncConnection) -> AsyncPostgresSessionProvider:
    return _TransactionalSessionProvider(db_connection, storage_type='postgres')


@pytest.fixture
async def session(session_provider: AsyncPostgresSessionProvider) -> AsyncGenerator[AsyncSession]:
    """Open a single AsyncSession for the duration of a test."""
    async with session_provider.session() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup_factory_session(session: AsyncSession) -> None:
    """Automatically wire the shared session into PostgresTaskFactory."""
    PostgresTaskFactory.__async_session__ = session


@pytest.fixture
async def task_service(
    session_provider: AsyncPostgresSessionProvider,
) -> AbstractTaskRepository:
    return TaskRepository(session_provider=session_provider, task_model=PostgresTask)

import os
import uuid
from contextlib import suppress

import pytest
import sqlalchemy as sa
from sqlalchemy_utils import create_database, database_exists, drop_database

from taskiq_dashboard.domain.services.task_service import TaskRepository
from taskiq_dashboard.infrastructure import get_settings
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.services.task_service import PostgresTaskRepository
from taskiq_dashboard.infrastructure.settings import PostgresSettings


@pytest.fixture(scope='session')
def postgres() -> PostgresSettings:
    """
    Creates a temporary database for tests
    """
    settings = get_settings()

    tmp_name = f'{uuid.uuid4().hex}.pytest'
    settings.postgres.database = tmp_name
    os.environ['POSTGRES__DATABASE'] = tmp_name
    settings.postgres.driver = 'postgresql'
    tmp_url = settings.postgres.dsn.get_secret_value()
    settings.postgres.driver = 'postgresql+asyncpg'

    if not database_exists(tmp_url):
        create_database(tmp_url)
    try:
        yield settings.postgres
    finally:
        with suppress(Exception):
            drop_database(tmp_url)


@pytest.fixture
async def database(postgres: PostgresSettings) -> str:
    session_provider = AsyncPostgresSessionProvider(connection_settings=postgres)
    await SchemaService(session_provider).create_schema()
    return postgres


@pytest.fixture
async def session_provider(database: PostgresSettings) -> AsyncPostgresSessionProvider:
    session_provider = AsyncPostgresSessionProvider(connection_settings=database)
    yield session_provider
    await session_provider.close()


@pytest.fixture(autouse=True)
async def cleanup_database(session_provider: AsyncPostgresSessionProvider) -> None:
    """Clean up database before each test"""
    async with session_provider.session() as session:
        await session.execute(sa.delete(PostgresTask))
        await session.commit()

    yield

    # Cleanup after test
    async with session_provider.session() as session:
        await session.execute(sa.delete(PostgresTask))
        await session.commit()


@pytest.fixture
async def task_service(
    session_provider: AsyncPostgresSessionProvider,
) -> TaskRepository:
    return PostgresTaskRepository(session_provider=session_provider)

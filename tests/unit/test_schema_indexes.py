from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateIndex

from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.settings import ColumnSettings


@pytest.fixture
def schema_service() -> SchemaService:
    provider = AsyncMock(storage_type='postgres')
    return SchemaService(provider, column_settings=ColumnSettings(manage_indexes=True))


async def test_when_another_replica_builds_indexes__then_skip_without_waiting(schema_service) -> None:
    connection = AsyncMock()
    connection.scalar.return_value = False
    await schema_service._sync_postgres_indexes(connection)
    connection.execute.assert_not_awaited()


async def test_when_extension_is_denied__then_build_only_btree_indexes(schema_service, caplog) -> None:
    connection = AsyncMock()
    connection.scalar.return_value = True

    async def execute(statement, *args):
        if str(statement).startswith('CREATE EXTENSION'):
            raise DBAPIError(str(statement), {}, Exception('permission denied'), connection_invalidated=False)
        return AsyncMock()

    connection.execute.side_effect = execute
    await schema_service._sync_postgres_indexes(connection)
    statements = [call.args[0] for call in connection.execute.await_args_list]
    indexes = [statement for statement in statements if isinstance(statement, CreateIndex)]
    assert len(indexes) == 4
    for statement in indexes:
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert 'CONCURRENTLY IF NOT EXISTS' in sql
        assert 'gin_trgm_ops' not in sql
    assert 'pg_trgm is unavailable' in caplog.text
    assert str(statements[-1]).startswith('SELECT pg_advisory_unlock')
    assert not PostgresTask.__table__.indexes


async def test_when_index_creation_fails__then_log_and_continue(schema_service, caplog) -> None:
    connection = AsyncMock()
    connection.scalar.return_value = True

    async def execute(statement, *args):
        if isinstance(statement, CreateIndex):
            raise DBAPIError(str(statement), {}, Exception('permission denied'), connection_invalidated=False)
        return AsyncMock()

    connection.execute.side_effect = execute
    await schema_service._sync_postgres_indexes(connection)
    assert 'Could not create optional index' in caplog.text
    statements = [call.args[0] for call in connection.execute.await_args_list]
    assert len([statement for statement in statements if isinstance(statement, CreateIndex)]) == 6
    assert str(statements[-1]).startswith('SELECT pg_advisory_unlock')
    assert not PostgresTask.__table__.indexes

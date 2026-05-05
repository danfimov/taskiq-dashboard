import uuid

import pytest
import sqlalchemy as sa

from taskiq_dashboard.infrastructure.database.schemas import SqliteTask, sa_metadata
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.repositories import TaskRepository
from taskiq_dashboard.infrastructure.settings import SqliteSettings


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_filtering_sqlite_tasks_by_argument_key_value_then_match_kwargs_only(tmp_path) -> None:
    sqlite_file = tmp_path / 'taskiq_dashboard_test.db'
    session_provider = AsyncPostgresSessionProvider(
        connection_settings=SqliteSettings(file_path=str(sqlite_file)),
    )
    async with session_provider.session() as session:
        connection = await session.connection()
        await connection.run_sync(sa_metadata.create_all, tables=[SqliteTask.__table__])
    repository = TaskRepository(session_provider=session_provider, task_model=SqliteTask)

    try:
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(SqliteTask),
                [
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_one',
                        'status': 1,
                        'worker': 'worker-1',
                        'args': ['approve', 'C6380048', 'u_legacy'],
                        'kwargs': {'entity_id': 'A-100', 'operation': 'create'},
                        'labels': {},
                    },
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_one',
                        'status': 1,
                        'worker': 'worker-1',
                        'args': [],
                        'kwargs': {'entity_id': 'A-200', 'operation': 'update'},
                        'labels': {},
                    },
                ],
            )

        filtered = await repository.find_tasks(
            task_name='task_one',
            arg_key='entity_id',
            arg_value='A-100',
        )

        assert len(filtered) == 1
        assert filtered[0].kwargs['entity_id'] == 'A-100'
    finally:
        await session_provider.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_requesting_sqlite_argument_keys_then_return_only_task_specific_kwargs_keys(tmp_path) -> None:
    sqlite_file = tmp_path / 'taskiq_dashboard_test.db'
    session_provider = AsyncPostgresSessionProvider(
        connection_settings=SqliteSettings(file_path=str(sqlite_file)),
    )
    async with session_provider.session() as session:
        connection = await session.connection()
        await connection.run_sync(sa_metadata.create_all, tables=[SqliteTask.__table__])
    repository = TaskRepository(session_provider=session_provider, task_model=SqliteTask)

    try:
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(SqliteTask),
                [
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_one',
                        'status': 1,
                        'worker': 'worker-1',
                        'args': [],
                        'kwargs': {'entity_id': 'A-100', 'operation': 'create'},
                        'labels': {},
                    },
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_two',
                        'status': 1,
                        'worker': 'worker-2',
                        'args': [],
                        'kwargs': {'external_id': 'EXT-1001'},
                        'labels': {},
                    },
                ],
            )

        keys = await repository.find_argument_keys(task_name='task_one')
        assert keys == ['entity_id', 'operation']
    finally:
        await session_provider.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_when_filtering_sqlite_without_task_name_then_ignore_arg_key_value_filter(tmp_path) -> None:
    sqlite_file = tmp_path / 'taskiq_dashboard_test.db'
    session_provider = AsyncPostgresSessionProvider(
        connection_settings=SqliteSettings(file_path=str(sqlite_file)),
    )
    async with session_provider.session() as session:
        connection = await session.connection()
        await connection.run_sync(sa_metadata.create_all, tables=[SqliteTask.__table__])
    repository = TaskRepository(session_provider=session_provider, task_model=SqliteTask)

    try:
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(SqliteTask),
                [
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_one',
                        'status': 1,
                        'worker': 'worker-1',
                        'args': [],
                        'kwargs': {'entity_id': 'A-100'},
                        'labels': {},
                    },
                    {
                        'id': uuid.uuid4(),
                        'name': 'task_two',
                        'status': 1,
                        'worker': 'worker-2',
                        'args': [],
                        'kwargs': {'entity_id': 'A-200'},
                        'labels': {},
                    },
                ],
            )

        filtered = await repository.find_tasks(
            task_name='',
            arg_key='entity_id',
            arg_value='A-100',
        )

        assert len(filtered) == 2
    finally:
        await session_provider.close()

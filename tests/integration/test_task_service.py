import datetime as dt
import uuid

import sqlalchemy as sa

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskRepository
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class TestTaskService:
    async def test_when_task_table_is_empty__then_return_empty_list(
        self,
        task_service: TaskRepository,
    ) -> None:
        # Given & When
        tasks = await task_service.find_tasks()

        # Then
        assert tasks == []

    async def test_when_getting_task_by_id_and_task_exists__then_return_task(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        now = dt.datetime.now(dt.UTC)

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    id=task_id,
                    name='test_task',
                    status=TaskStatus.QUEUED,
                    worker='test_worker',
                    args='[]',
                    kwargs='{}',
                    queued_at=now,
                    started_at=now,
                )
            )
            await session.commit()

        # When
        result = await task_service.get_task_by_id(task_id)

        # Then
        assert result is not None
        assert result.id == task_id
        assert result.name == 'test_task'
        assert result.status == TaskStatus.QUEUED
        assert result.worker == 'test_worker'

    async def test_when_getting_task_by_id_and_task_does_not_exist__then_return_none(
        self,
        task_service: TaskRepository,
    ) -> None:
        # Given
        non_existent_id = uuid.uuid4()

        # When
        result = await task_service.get_task_by_id(non_existent_id)

        # Then
        assert result is None

    async def test_when_creating_task__then_task_is_stored_with_queued_status(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        now = dt.datetime.now(dt.UTC)
        queued_task = QueuedTask(
            task_name='process_data',
            worker='worker_1',
            args=['arg1', 'arg2'],
            kwargs={'key1': 'value1'},
            queued_at=now,
        )

        # When
        await task_service.create_task(task_id, queued_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.name == 'process_data'
        assert task_row.worker == 'worker_1'
        assert task_row.status == TaskStatus.QUEUED
        assert task_row.queued_at == now

    async def test_when_updating_task_with_started_task__then_task_status_is_in_progress(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        queued_time = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=10)
        started_time = dt.datetime.now(dt.UTC)

        # Create initial task
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    id=task_id,
                    name='old_name',
                    status=TaskStatus.QUEUED,
                    worker='worker_1',
                    args='[]',
                    kwargs='{}',
                    queued_at=queued_time,
                    started_at=queued_time,
                )
            )
            await session.commit()

        started_task = StartedTask(
            task_name='process_data',
            worker='worker_1',
            args=['arg1', 'arg2'],
            kwargs={'key1': 'value1'},
            started_at=started_time,
        )

        # When
        await task_service.update_task(task_id, started_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.started_at == started_time
        assert task_row.name == 'process_data'

    async def test_when_updating_task_with_executed_task_without_error__then_task_status_is_completed(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        queued_time = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=10)
        finished_time = dt.datetime.now(dt.UTC)

        # Create initial task
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    id=task_id,
                    name='process_data',
                    status=TaskStatus.IN_PROGRESS,
                    worker='worker_1',
                    args='[]',
                    kwargs='{}',
                    queued_at=queued_time,
                    started_at=queued_time,
                )
            )
            await session.commit()

        executed_task = ExecutedTask(
            finished_at=finished_time,
            execution_time=5.0,
            error=None,
            return_value={'return_value': 'success_result'},
        )

        # When
        await task_service.update_task(task_id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.COMPLETED
        assert task_row.finished_at == finished_time
        assert task_row.result == 'success_result'
        assert task_row.error is None

    async def test_when_updating_task_with_executed_task_with_error__then_task_status_is_failure(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        queued_time = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=10)
        finished_time = dt.datetime.now(dt.UTC)
        error_message = 'Task execution failed: Division by zero'

        # Create initial task
        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    id=task_id,
                    name='process_data',
                    status=TaskStatus.IN_PROGRESS,
                    worker='worker_1',
                    args='[]',
                    kwargs='{}',
                    queued_at=queued_time,
                    started_at=queued_time,
                )
            )
            await session.commit()

        executed_task = ExecutedTask(
            finished_at=finished_time,
            execution_time=2.5,
            error=error_message,
            return_value={},
        )

        # When
        await task_service.update_task(task_id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.FAILURE
        assert task_row.finished_at == finished_time
        assert task_row.error == error_message

    async def test_when_finding_tasks_with_status_filter__then_return_only_tasks_with_that_status(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        now = dt.datetime.now(dt.UTC)

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': 'task_1',
                            'status': TaskStatus.QUEUED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'task_2',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'task_3',
                            'status': TaskStatus.QUEUED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(status=TaskStatus.QUEUED)

        # Then
        assert len(tasks) == 2
        assert all(task.status == TaskStatus.QUEUED for task in tasks)

    async def test_when_finding_tasks_with_name_search__then_return_only_matching_tasks(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        now = dt.datetime.now(dt.UTC)

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': 'send_email_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'process_data_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'send_sms_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(name='send')

        # Then
        assert len(tasks) == 2
        assert all('send' in task.name for task in tasks)

    async def test_when_finding_tasks_with_pagination__then_return_correct_page(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        now = dt.datetime.now(dt.UTC)
        task_names = [f'task_{i}' for i in range(1, 76)]  # 75 tasks

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': name,
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        }
                        for name in task_names
                    ]
                )
            )
            await session.commit()

        # When - get first page with limit 30 and offset 0
        tasks_page_1 = await task_service.find_tasks(limit=30, offset=0)
        # When - get second page with offset 30
        tasks_page_2 = await task_service.find_tasks(limit=30, offset=30)
        # When - get third page with offset 60
        tasks_page_3 = await task_service.find_tasks(limit=30, offset=60)

        # Then
        assert len(tasks_page_1) == 30
        assert len(tasks_page_2) == 30
        assert len(tasks_page_3) == 15
        # Verify no overlap between pages
        page_1_ids = {task.id for task in tasks_page_1}
        page_2_ids = {task.id for task in tasks_page_2}
        page_3_ids = {task.id for task in tasks_page_3}
        assert page_1_ids.isdisjoint(page_2_ids)
        assert page_2_ids.isdisjoint(page_3_ids)

    async def test_when_finding_tasks_sorted_by_started_at_descending__then_return_tasks_in_correct_order(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        base_time = dt.datetime.now(dt.UTC)
        times = [base_time - dt.timedelta(seconds=i * 10) for i in range(5)]

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': f'task_{i}',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': times[i],
                            'started_at': times[i],
                        }
                        for i in range(5)
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(sort_by='started_at', sort_order='desc')

        # Then
        started_times = [task.started_at for task in tasks]
        assert started_times == sorted(started_times, reverse=True)

    async def test_when_finding_tasks_sorted_by_started_at_ascending__then_return_tasks_in_correct_order(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        base_time = dt.datetime.now(dt.UTC)
        times = [base_time - dt.timedelta(seconds=i * 10) for i in range(5)]

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': f'task_{i}',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': times[i],
                            'started_at': times[i],
                        }
                        for i in range(5)
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(sort_by='started_at', sort_order='asc')

        # Then
        started_times = [task.started_at for task in tasks]
        assert started_times == sorted(started_times)

    async def test_when_finding_tasks_sorted_by_finished_at_descending__then_return_tasks_in_correct_order(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        base_time = dt.datetime.now(dt.UTC)
        times = [base_time - dt.timedelta(seconds=i * 10) for i in range(5)]

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': f'task_{i}',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': times[i],
                            'started_at': times[i],
                            'finished_at': times[i],
                        }
                        for i in range(5)
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(sort_by='finished_at', sort_order='desc')

        # Then
        finished_times = [task.finished_at for task in tasks if task.finished_at is not None]
        assert finished_times == sorted(finished_times, reverse=True)

    async def test_when_finding_tasks_with_multiple_filters_applied__then_return_correct_tasks(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        now = dt.datetime.now(dt.UTC)

        async with session_provider.session() as session:
            await session.execute(
                sa.insert(PostgresTask).values(
                    [
                        {
                            'id': uuid.uuid4(),
                            'name': 'send_email_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'send_email_task',
                            'status': TaskStatus.QUEUED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'process_data_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                        {
                            'id': uuid.uuid4(),
                            'name': 'send_sms_task',
                            'status': TaskStatus.COMPLETED,
                            'worker': 'worker_1',
                            'args': '[]',
                            'kwargs': '{}',
                            'queued_at': now,
                            'started_at': now,
                        },
                    ]
                )
            )
            await session.commit()

        # When
        tasks = await task_service.find_tasks(
            status=TaskStatus.COMPLETED,
            name='send',
        )

        # Then
        assert len(tasks) == 2
        assert all(task.status == TaskStatus.COMPLETED for task in tasks)
        assert all('send' in task.name for task in tasks)

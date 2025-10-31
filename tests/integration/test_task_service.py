import datetime as dt
import uuid

import sqlalchemy as sa
from polyfactory import Use
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskRepository
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class PostgresTaskFactory(SQLAlchemyFactory[PostgresTask]):
    __check_model__ = True
    __set_relationships__ = False

    status = Use(SQLAlchemyFactory.__random__.choice, [task_status.value for task_status in TaskStatus])


class TestTaskService:
    async def test_when_task_batch_update__then_update_task_statuses(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        tasks_queued = await PostgresTaskFactory.create_batch_async(2, status=TaskStatus.QUEUED.value)

        # When
        await task_service.batch_update(
            old_status=TaskStatus.QUEUED,
            new_status=TaskStatus.ABANDONED,
        )

        # Then
        async with session_provider.session() as session:
            result = await session.execute(
                sa.select(PostgresTask).where(PostgresTask.id.in_([task.id for task in tasks_queued]))
            )
            updated_tasks = result.scalars().all()
            for task in updated_tasks:
                assert task.status == TaskStatus.ABANDONED

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        task = await PostgresTaskFactory.create_async()

        # When
        result = await task_service.get_task_by_id(task.id)

        # Then
        assert result is not None
        assert result.id == task.id
        assert result.name == task.name
        assert result.status == task.status
        assert result.worker == task.worker

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
        now = dt.datetime.now(dt.timezone.utc)
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
        PostgresTaskFactory.__async_session__ = session_provider.session
        task_queued = await PostgresTaskFactory.create_async(
            status=TaskStatus.QUEUED.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10),
            started_at=None,
        )
        started_task = StartedTask(
            task_name='process_data',
            worker='worker_1',
            args=['arg1', 'arg2'],
            kwargs={'key1': 'value1'},
            started_at=dt.datetime.now(dt.timezone.utc),
        )

        # When
        await task_service.update_task(task_queued.id, started_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_queued.id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.started_at == started_task.started_at
        assert task_row.name == 'process_data'

    async def test_when_updating_task_with_executed_task_without_error__then_task_status_is_completed(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        task_in_progress = await PostgresTaskFactory.create_async(
            status=TaskStatus.IN_PROGRESS.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10),
            started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5),
        )
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=5.0,
            error=None,
            return_value={'return_value': 'success_result'},
        )

        # When
        await task_service.update_task(task_in_progress.id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_in_progress.id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.COMPLETED
        assert task_row.finished_at == executed_task.finished_at
        assert task_row.result == 'success_result'
        assert task_row.error is None

    async def test_when_updating_task_with_executed_task_with_error__then_task_status_is_failure(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        task_in_progress = await PostgresTaskFactory.create_async(
            status=TaskStatus.IN_PROGRESS.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10),
            started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5),
        )
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=2.5,
            error='Task execution failed: Division by zero',
            return_value={},
        )

        # When
        await task_service.update_task(task_in_progress.id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_in_progress.id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.FAILURE
        assert task_row.finished_at == executed_task.finished_at
        assert task_row.error == executed_task.error

    async def test_when_finding_tasks_with_status_filter__then_return_only_tasks_with_that_status(
        self,
        task_service: TaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(2, status=TaskStatus.QUEUED.value)
        await PostgresTaskFactory.create_async(status=TaskStatus.IN_PROGRESS.value)
        await PostgresTaskFactory.create_async(status=TaskStatus.ABANDONED.value)
        await PostgresTaskFactory.create_async(status=TaskStatus.FAILURE.value)
        await PostgresTaskFactory.create_async(status=TaskStatus.COMPLETED.value)

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(2, name='send_email')
        await PostgresTaskFactory.create_async(name='process_data')

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(13)

        # When - get first page with limit 30 and offset 0
        tasks_page_1 = await task_service.find_tasks(limit=5, offset=0)
        # When - get second page with offset 30
        tasks_page_2 = await task_service.find_tasks(limit=5, offset=5)
        # When - get third page with offset 60
        tasks_page_3 = await task_service.find_tasks(limit=5, offset=10)

        # Then
        assert len(tasks_page_1) == 5
        assert len(tasks_page_2) == 5
        assert len(tasks_page_3) == 3
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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(5)

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(5)

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(5)

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
        PostgresTaskFactory.__async_session__ = session_provider.session
        await PostgresTaskFactory.create_batch_async(2, name='send_email_task', status=TaskStatus.COMPLETED.value)
        await PostgresTaskFactory.create_batch_async(2, name='publish_data', status=TaskStatus.COMPLETED.value)
        await PostgresTaskFactory.create_batch_async(2, name='send_progress', status=TaskStatus.IN_PROGRESS.value)

        # When
        tasks = await task_service.find_tasks(
            status=TaskStatus.COMPLETED,
            name='send',
        )

        # Then
        assert len(tasks) == 2
        assert all(task.status == TaskStatus.COMPLETED for task in tasks)
        assert all('send' in task.name for task in tasks)

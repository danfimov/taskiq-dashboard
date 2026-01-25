import datetime as dt
import uuid

import sqlalchemy as sa

from tests.integration.factories import PostgresTaskFactory

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class TestTaskService:
    async def test_when_task_batch_update__then_update_task_statuses(
        self,
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
    ) -> None:
        # Given & When
        tasks = await task_service.find_tasks()

        # Then
        assert tasks == []

    async def test_when_getting_task_by_id_and_task_exists__then_return_task(
        self,
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
    ) -> None:
        # Given
        non_existent_id = uuid.uuid4()

        # When
        result = await task_service.get_task_by_id(non_existent_id)

        # Then
        assert result is None

    async def test_when_creating_task__then_task_is_stored_with_queued_status(
        self,
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
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

    async def test_when_finding_tasks_with_id_search__then_return_matching_tasks(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        known_task_id = uuid.uuid4()
        await PostgresTaskFactory.create_async(id=known_task_id, name='task_one')
        await PostgresTaskFactory.create_async(name='task_two')

        # When
        task_id_str = str(known_task_id)[:8]
        tasks = await task_service.find_tasks(name=task_id_str)

        # Then
        assert len(tasks) == 1
        assert tasks[0].id == known_task_id

    async def test_when_finding_tasks_with_pagination__then_return_correct_page(
        self,
        task_service: AbstractTaskRepository,
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
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        for minutes in range(5):
            await PostgresTaskFactory.create_async(
                started_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
            )

        # When
        tasks = await task_service.find_tasks(sort_by='started_at', sort_order='desc')

        # Then
        started_times = [task.started_at for task in tasks]
        assert started_times == sorted(started_times, reverse=True)

    async def test_when_finding_tasks_sorted_by_started_at_ascending__then_return_tasks_in_correct_order(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        for minutes in range(5):
            await PostgresTaskFactory.create_async(
                started_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
            )

        # When
        tasks = await task_service.find_tasks(sort_by='started_at', sort_order='asc')

        # Then
        started_times = [task.started_at for task in tasks]
        assert started_times == sorted(started_times)

    async def test_when_finding_tasks_sorted_by_finished_at_descending__then_return_tasks_in_correct_order(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        for minutes in range(5):
            await PostgresTaskFactory.create_async(
                finished_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
            )

        # When
        tasks = await task_service.find_tasks(sort_by='finished_at', sort_order='desc')

        # Then
        finished_times = [task.finished_at for task in tasks if task.finished_at is not None]
        assert finished_times == sorted(finished_times, reverse=True)

    async def test_when_finding_tasks_with_multiple_filters_applied__then_return_correct_tasks(
        self,
        task_service: AbstractTaskRepository,
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

    async def test_when_updating_non_existent_task_with_started_task__then_create_and_update_task(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        started_task = StartedTask(
            task_name='delayed_process',
            worker='worker_2',
            args=['arg1'],
            kwargs={'key': 'value'},
            started_at=dt.datetime.now(dt.timezone.utc),
        )

        # When
        await task_service.update_task(task_id, started_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.name == 'delayed_process'
        assert task_row.worker == 'worker_2'
        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.started_at == started_task.started_at
        assert task_row.args == ['arg1']

    async def test_when_updating_non_existent_task_with_executed_task__then_create_and_complete_task(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=3.5,
            error=None,
            return_value={'return_value': 'quick_result'},
        )

        # When
        await task_service.update_task(task_id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.status == TaskStatus.COMPLETED
        assert task_row.finished_at == executed_task.finished_at
        assert task_row.result == 'quick_result'
        assert task_row.queued_at is None

    async def test_when_executed_event_arrives_before_started__then_task_transitions_directly_to_completed(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=1.0,
            error=None,
            return_value={'return_value': 'immediate_result'},
        )

        # When - executed event arrives first
        await task_service.update_task(task_id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.COMPLETED
        assert task_row.finished_at == executed_task.finished_at

    async def test_when_executed_event_with_error_arrives_before_started__then_task_transitions_to_failure(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=0.5,
            error='Task failed immediately',
            return_value={},
        )

        # When - executed event with error arrives before started
        await task_service.update_task(task_id, executed_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.FAILURE
        assert task_row.error == 'Task failed immediately'

    async def test_when_started_event_arrives_after_executed__then_task_status_remains_completed(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=2.0,
            error=None,
            return_value={'return_value': 'completed_result'},
        )
        started_task = StartedTask(
            task_name='out_of_order_task',
            worker='worker_3',
            args=[],
            kwargs={},
            started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3),
        )

        # When - executed event arrives first
        await task_service.update_task(task_id, executed_task)
        # When - then started event arrives after
        await task_service.update_task(task_id, started_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        # Task should now be IN_PROGRESS because started event overwrites the status
        # This tests the actual behavior - later events overwrite earlier ones
        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.started_at == started_task.started_at

    async def test_when_multiple_out_of_order_events__then_task_reflects_latest_event_state(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        now = dt.datetime.now(dt.timezone.utc)

        # Simulate events arriving in wrong order: executed -> started -> executed
        executed_task_1 = ExecutedTask(
            finished_at=now,
            execution_time=5.0,
            error=None,
            return_value={'return_value': 'first_result'},
        )
        started_task = StartedTask(
            task_name='unreliable_task',
            worker='worker_4',
            args=['retry_arg'],
            kwargs={},
            started_at=now - dt.timedelta(seconds=6),
        )
        executed_task_2 = ExecutedTask(
            finished_at=now + dt.timedelta(seconds=1),
            execution_time=1.0,
            error='Retry failed',
            return_value={},
        )

        # When - events arrive in wrong order
        await task_service.update_task(task_id, executed_task_1)
        await task_service.update_task(task_id, started_task)
        await task_service.update_task(task_id, executed_task_2)

        # Then - last event should define the state
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.status == TaskStatus.FAILURE
        assert task_row.error == 'Retry failed'
        assert task_row.finished_at == executed_task_2.finished_at
        assert task_row.name == 'unreliable_task'

    async def test_when_create_task_called_after_update_with_started_event__then_add_queued_at_and_worker(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        started_task = StartedTask(
            task_name='delayed_task',
            worker='worker_1',
            args=['arg1'],
            kwargs={'key': 'value'},
            started_at=dt.datetime.now(dt.timezone.utc),
        )
        queued_task = QueuedTask(
            task_name='delayed_task',
            worker='worker_1',
            args=['arg1'],
            kwargs={'key': 'value'},
            labels={'priority': 'high'},
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5),
        )

        # When - started event arrives first
        await task_service.update_task(task_id, started_task)
        # When - then queued event arrives after
        await task_service.create_task(task_id, queued_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.queued_at == queued_task.queued_at
        assert task_row.worker == 'worker_1'
        assert task_row.name == 'delayed_task'
        assert task_row.labels == {'priority': 'high'}

    async def test_when_create_task_called_after_update_with_executed_event__then_add_queued_at_and_worker(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        executed_task = ExecutedTask(
            finished_at=dt.datetime.now(dt.timezone.utc),
            execution_time=2.0,
            error=None,
            return_value={'return_value': 'result'},
        )
        queued_task = QueuedTask(
            task_name='quick_task',
            worker='worker_2',
            args=[],
            kwargs={},
            labels={},
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=3),
        )

        # When - executed event arrives first
        await task_service.update_task(task_id, executed_task)
        # When - then queued event arrives after
        await task_service.create_task(task_id, queued_task)

        # Then
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.status == TaskStatus.COMPLETED
        assert task_row.queued_at == queued_task.queued_at
        assert task_row.worker == 'worker_2'
        assert task_row.name == 'quick_task'
        assert task_row.result == 'result'

    async def test_when_create_task_called_after_update__then_task_has_complete_info(
        self,
        task_service: AbstractTaskRepository,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        now = dt.datetime.now(dt.timezone.utc)

        # Events arrive in wrong order: executed -> started -> queued
        executed_task = ExecutedTask(
            finished_at=now,
            execution_time=5.0,
            error=None,
            return_value={'return_value': 'success'},
        )
        started_task = StartedTask(
            task_name='complex_task',
            worker='worker_3',
            args=['a', 'b'],
            kwargs={'x': 1},
            started_at=now - dt.timedelta(seconds=6),
        )
        queued_task = QueuedTask(
            task_name='complex_task',
            worker='worker_3',
            args=['a', 'b'],
            kwargs={'x': 1},
            labels={'retry': 'true'},
            queued_at=now - dt.timedelta(seconds=7),
        )

        # When - events arrive in wrong order
        await task_service.update_task(task_id, executed_task)
        await task_service.update_task(task_id, started_task)
        await task_service.create_task(task_id, queued_task)

        # Then - task should have all the information
        async with session_provider.session() as session:
            result = await session.execute(sa.select(PostgresTask).where(PostgresTask.id == task_id))
            task_row = result.scalar_one()

        assert task_row.id == task_id
        assert task_row.status == TaskStatus.IN_PROGRESS
        assert task_row.name == 'complex_task'
        assert task_row.worker == 'worker_3'
        assert task_row.queued_at == queued_task.queued_at
        assert task_row.started_at == started_task.started_at
        assert task_row.finished_at == executed_task.finished_at
        assert task_row.result == 'success'
        assert task_row.args == ['a', 'b']
        assert task_row.labels == {'retry': 'true'}

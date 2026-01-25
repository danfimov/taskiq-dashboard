import datetime as dt

import sqlalchemy as sa

from tests.integration.factories import PostgresTaskFactory

from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.services.cleanup_service import CleanupService
from taskiq_dashboard.infrastructure.settings import CleanupSettings


class TestCleanupService:
    @staticmethod
    async def _task_exists(session_provider: AsyncPostgresSessionProvider, task_id) -> bool:
        """Helper to check if a task exists in the database."""
        async with session_provider.session() as session:
            result = await session.execute(
                sa.select(PostgresTask.id).where(PostgresTask.id == task_id)
            )
            return result.scalar_one_or_none() is not None

    async def test_when_cleanup_disabled__then_no_tasks_deleted(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(is_enabled=False)
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )
        await PostgresTaskFactory.create_batch_async(
            5,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60),
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 0
        assert result.deleted_by_count == 0

    async def test_when_cleanup_by_ttl__then_old_tasks_deleted(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=30,
            max_tasks=10000,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create old tasks (older than 30 days)
        old_tasks = await PostgresTaskFactory.create_batch_async(
            3,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=45),
        )

        # Create recent tasks (within 30 days)
        recent_tasks = await PostgresTaskFactory.create_batch_async(
            2,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5),
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 3
        assert result.deleted_by_count == 0

        # Verify old tasks were deleted
        for task in old_tasks:
            found = await self._task_exists(session_provider, task.id)
            assert not found, f'Old task {task.id} should have been deleted'

        # Verify recent tasks still exist
        for task in recent_tasks:
            found = await self._task_exists(session_provider, task.id)
            assert found, f'Recent task {task.id} should still exist'

    async def test_when_cleanup_by_ttl__then_tasks_without_finished_at_use_queued_at(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=30,
            max_tasks=10000,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create old task with only queued_at (simulating stuck task)
        old_stuck_task = await PostgresTaskFactory.create_async(
            status=TaskStatus.QUEUED.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=45),
            started_at=None,
            finished_at=None,
        )

        # Create recent task with only queued_at
        recent_stuck_task = await PostgresTaskFactory.create_async(
            status=TaskStatus.QUEUED.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5),
            started_at=None,
            finished_at=None,
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 1

        # Verify old stuck task was deleted
        found = await self._task_exists(session_provider, old_stuck_task.id)
        assert not found, 'Old stuck task should have been deleted'

        # Verify recent stuck task still exists
        found = await self._task_exists(session_provider, recent_stuck_task.id)
        assert found, 'Recent stuck task should still exist'

    async def test_when_cleanup_by_ttl__then_in_progress_tasks_also_deleted_if_old(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=30,
            max_tasks=10000,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create old in-progress task (should be deleted - prevents DB bloat from stuck tasks)
        old_in_progress_task = await PostgresTaskFactory.create_async(
            status=TaskStatus.IN_PROGRESS.value,
            queued_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=45),
            started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=44),
            finished_at=None,
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 1

        found = await self._task_exists(session_provider, old_in_progress_task.id)
        assert not found, 'Old in-progress task should have been deleted'

    async def test_when_cleanup_by_count__then_oldest_tasks_deleted(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=365,  # High TTL so it doesn't affect count-based cleanup
            max_tasks=3,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create 5 tasks with different ages
        old_task_1 = await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10),
        )
        old_task_2 = await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8),
        )
        recent_task_1 = await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3),
        )
        recent_task_2 = await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2),
        )
        recent_task_3 = await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 0
        assert result.deleted_by_count == 2  # 5 tasks - 3 max = 2 to delete

        # Verify oldest tasks were deleted
        found = await self._task_exists(session_provider, old_task_1.id)
        assert not found, 'Oldest task should have been deleted'
        found = await self._task_exists(session_provider, old_task_2.id)
        assert not found, 'Second oldest task should have been deleted'

        # Verify recent tasks still exist
        for task in [recent_task_1, recent_task_2, recent_task_3]:
            found = await self._task_exists(session_provider, task.id)
            assert found, f'Recent task {task.id} should still exist'

    async def test_when_task_count_below_max__then_no_tasks_deleted_by_count(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=365,
            max_tasks=10,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create only 3 tasks (below max_tasks=10)
        tasks = await PostgresTaskFactory.create_batch_async(
            3,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5),
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_count == 0

        # Verify all tasks still exist
        for task in tasks:
            found = await self._task_exists(session_provider, task.id)
            assert found, f'Task {task.id} should still exist'

    async def test_when_both_ttl_and_count_cleanup__then_both_applied(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(
            is_enabled=True,
            ttl_days=30,
            max_tasks=2,
        )
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        # Create 2 old tasks (will be deleted by TTL)
        await PostgresTaskFactory.create_batch_async(
            2,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=45),
        )

        # Create 4 recent tasks (2 will be deleted by count after TTL cleanup)
        await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10),
        )
        await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8),
        )
        await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3),
        )
        await PostgresTaskFactory.create_async(
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
        )

        # When
        result = await cleanup_service.cleanup()

        # Then
        assert result.deleted_by_ttl == 2  # 2 old tasks
        assert result.deleted_by_count == 2  # 4 recent tasks - 2 max = 2 to delete

    async def test_cleanup_by_ttl_direct__then_returns_deleted_count(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(is_enabled=True)
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        await PostgresTaskFactory.create_batch_async(
            3,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=15),
        )

        # When - call cleanup_by_ttl directly with 10 days
        deleted_count = await cleanup_service.cleanup_by_ttl(ttl_days=10)

        # Then
        assert deleted_count == 3

    async def test_cleanup_by_count_direct__then_returns_deleted_count(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        # Given
        PostgresTaskFactory.__async_session__ = session_provider.session
        settings = CleanupSettings(is_enabled=True)
        cleanup_service = CleanupService(
            session_provider=session_provider,
            task_model=PostgresTask,
            settings=settings,
        )

        await PostgresTaskFactory.create_batch_async(
            5,
            status=TaskStatus.COMPLETED.value,
            finished_at=dt.datetime.now(dt.timezone.utc),
        )

        # When - call cleanup_by_count directly with max_tasks=2
        deleted_count = await cleanup_service.cleanup_by_count(max_tasks=2)

        # Then
        assert deleted_count == 3  # 5 - 2 = 3 deleted

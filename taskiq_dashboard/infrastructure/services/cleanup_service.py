import asyncio
import contextlib
import datetime as dt
import logging

import sqlalchemy as sa

from taskiq_dashboard.domain.services.cleanup_service import AbstractCleanupService, CleanupResult
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.settings import CleanupSettings


logger = logging.getLogger(__name__)


class CleanupService(AbstractCleanupService):
    """Service for cleaning up old tasks from the database."""

    def __init__(
        self,
        session_provider: AsyncPostgresSessionProvider,
        task_model: type[PostgresTask] | type[SqliteTask],
        settings: CleanupSettings,
    ) -> None:
        self._session_provider = session_provider
        self._task = task_model
        self._settings = settings

    async def cleanup(self) -> CleanupResult:
        if not self._settings.is_enabled:
            return CleanupResult()

        result = CleanupResult()
        result.deleted_by_ttl = await self.cleanup_by_ttl(self._settings.ttl_days)
        result.deleted_by_count = await self.cleanup_by_count(self._settings.max_tasks)

        logger.info(
            'Cleanup completed: deleted %d tasks (TTL: %d, count limit: %d)',
            result.deleted_by_ttl + result.deleted_by_count,
            result.deleted_by_ttl,
            result.deleted_by_count,
        )

        return result

    async def cleanup_by_ttl(self, ttl_days: int) -> int:
        cutoff_date = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=ttl_days)
        task_timestamp = sa.func.coalesce(
            self._task.finished_at,
            self._task.started_at,
            self._task.queued_at,
        )
        query = sa.delete(self._task).where(task_timestamp < cutoff_date)
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            return result.rowcount or 0  # type: ignore[possibly-missing-attribute]

    async def cleanup_by_count(self, max_tasks: int) -> int:
        count_query = sa.select(sa.func.count()).select_from(self._task)
        async with self._session_provider.session() as session:
            result = await session.execute(count_query)
            total_count = result.scalar() or 0

        if total_count <= max_tasks:
            return 0

        tasks_to_delete = total_count - max_tasks
        task_timestamp = sa.func.coalesce(
            self._task.finished_at,
            self._task.started_at,
            self._task.queued_at,
        )
        subquery = (
            sa.select(self._task.id)
            .order_by(task_timestamp.asc())
            .limit(tasks_to_delete)
        )
        delete_query = sa.delete(self._task).where(self._task.id.in_(subquery))
        async with self._session_provider.session() as session:
            result = await session.execute(delete_query)
            return result.rowcount or 0  # type: ignore[possibly-missing-attribute]


class PeriodicCleanupRunner:
    """Background task runner for periodic cleanup."""

    def __init__(
        self,
        cleanup_service: AbstractCleanupService,
        interval_hours: int,
    ) -> None:
        self._cleanup_service = cleanup_service
        self._interval_seconds = interval_hours * 3600
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the periodic cleanup background task."""
        self._task = asyncio.create_task(self._run())
        logger.info('Periodic cleanup started with interval %d hours', self._interval_seconds // 3600)

    async def stop(self) -> None:
        """Stop the periodic cleanup background task gracefully."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info('Periodic cleanup stopped')

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval_seconds,
                )
            except asyncio.TimeoutError:  # noqa: PERF203
                try:
                    await self._cleanup_service.cleanup()
                except Exception:
                    logger.exception('Error during periodic cleanup')

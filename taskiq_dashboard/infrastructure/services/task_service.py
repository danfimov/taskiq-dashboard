import uuid

import sqlalchemy as sa

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskService
from taskiq_dashboard.infrastructure.database.schemas import Task as TaskSchema
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class SqlAlchemyTaskService(TaskService):
    def __init__(self, session_provider: AsyncPostgresSessionProvider) -> None:
        self._session_provider = session_provider

    async def get_tasks(  # noqa: PLR0913
        self,
        page: int = 1,
        per_page: int = 30,
        status: TaskStatus | None = None,
        name_search: str | None = None,
        sort_by: str | None = None,
        sort_order: str = 'desc',
    ) -> tuple[list[Task], int]:
        """
        Get paginated and filtered tasks.

        Args:
            page: Page number (1-indexed)
            per_page: Number of tasks per page
            status: Filter by task status
            name_search: Filter by task name (fuzzy search)
            sort_by: Column to sort by ('started_at', 'finished_at', or None for default)
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Tuple of (tasks_list, total_count)
        """
        # Build base query with filters
        query = sa.select(TaskSchema)
        count_query = sa.select(sa.func.count(TaskSchema.id))

        # Apply status filter
        if status is not None:
            query = query.where(TaskSchema.status == status)
            count_query = count_query.where(TaskSchema.status == status)

        # Apply name search filter
        if name_search and name_search.strip():
            # Use ILIKE for case-insensitive pattern matching (PostgreSQL specific)
            search_pattern = f'%{name_search.strip()}%'
            query = query.where(TaskSchema.name.ilike(search_pattern))
            count_query = count_query.where(TaskSchema.name.ilike(search_pattern))

        # Get total count with applied filters
        async with self._session_provider.session() as session:
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar()
            total_count = total_count or 0

        # Calculate offset
        offset = (page - 1) * per_page

        # Apply sorting
        if sort_by == 'finished_at':
            sort_column = TaskSchema.finished_at
        elif sort_by == 'started_at':
            sort_column = TaskSchema.started_at
        else:
            sort_column = TaskSchema.started_at

        query = query.order_by(sort_column.asc()) if sort_order.lower() == 'asc' else query.order_by(sort_column.desc())

        # Get tasks for current page
        query = query.limit(per_page).offset(offset)

        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task_schemas = result.scalars().all()

        # Convert to DTOs
        tasks = [Task.model_validate(task) for task in task_schemas]

        return tasks, total_count

    async def get_task_by_id(self, task_id: uuid.UUID) -> Task | None:
        query = sa.select(TaskSchema).where(TaskSchema.id == task_id)
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task = result.scalar_one_or_none()

        if not task:
            return None

        return Task.model_validate(task)

    async def create_task(
        self,
        task_id: str,
        task_arguments: QueuedTask,
    ) -> None:
        query = sa.insert(TaskSchema).values(
            id=task_id,
            name=task_arguments.task_name,
            status=TaskStatus.QUEUED,
            worker=task_arguments.worker,
            args=task_arguments.args,
            kwargs=task_arguments.kwargs,
            queued_at=task_arguments.queued_at,
        )
        async with self._session_provider.session() as session:
            await session.execute(query)

    async def update_task(
        self,
        task_id: str,
        task_arguments: StartedTask | ExecutedTask,
    ) -> None:
        query = sa.update(TaskSchema).where(TaskSchema.id == task_id)

        if isinstance(task_arguments, StartedTask):
            task_status = TaskStatus.IN_PROGRESS
            query = query.values(
                status=task_status,
                started_at=task_arguments.started_at,
                args=task_arguments.args,
                kwargs=task_arguments.kwargs,
                name=task_arguments.task_name,
                worker=task_arguments.worker,
            )
        else:
            task_status = TaskStatus.FAILURE if task_arguments.error is not None else TaskStatus.COMPLETED
            query = query.values(
                status=task_status,
                finished_at=task_arguments.finished_at,
                result=task_arguments.return_value.get('return_value'),
                error=task_arguments.error,
            )
        async with self._session_provider.session() as session:
            await session.execute(query)

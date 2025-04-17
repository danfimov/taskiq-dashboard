import typing as tp
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_

from taskiq_dashboard.domain.dto.task import Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskService
from taskiq_dashboard.infrastructure.database.schemas import Task as TaskSchema


class SqlAlchemyTaskService(TaskService):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_tasks(
        self,
        page: int = 1,
        per_page: int = 30,
        status: TaskStatus | None = None,
        name_search: str | None = None,
    ) -> tuple[list[Task], int]:
        """
        Get paginated and filtered tasks.

        Args:
            page: Page number (1-indexed)
            per_page: Number of tasks per page
            status: Filter by task status
            name_search: Filter by task name (fuzzy search)

        Returns:
            Tuple of (tasks_list, total_count)
        """
        # Build base query with filters
        query = select(TaskSchema)
        count_query = select(func.count(TaskSchema.id))

        # Apply status filter
        if status is not None:
            query = query.where(TaskSchema.status == status)
            count_query = count_query.where(TaskSchema.status == status)

        # Apply name search filter
        if name_search and name_search.strip():
            # Use ILIKE for case-insensitive pattern matching (PostgreSQL specific)
            search_pattern = f"%{name_search.strip()}%"
            query = query.where(TaskSchema.name.ilike(search_pattern))
            count_query = count_query.where(TaskSchema.name.ilike(search_pattern))

        # Get total count with applied filters
        total_count_result = await self.session.execute(count_query)
        total_count = total_count_result.scalar()

        # Calculate offset
        offset = (page - 1) * per_page

        # Get tasks for current page
        query = (
            query
            .order_by(TaskSchema.started_at.desc())
            .limit(per_page)
            .offset(offset)
        )
        result = await self.session.execute(query)
        task_schemas = result.scalars().all()

        # Convert to DTOs
        tasks = [
            Task.model_validate(task)
            for task in task_schemas
        ]

        return tasks, total_count

    async def get_task_by_id(self, task_id: uuid.UUID) -> Task | None:
        query = select(TaskSchema).where(TaskSchema.id == task_id)
        result = await self.session.execute(query)
        task = result.scalar_one_or_none()

        if not task:
            return None

        return Task.model_validate(task)

    async def get_all_tasks(self) -> list[Task]:
        """Get all tasks without pagination."""
        tasks, _ = await self.get_tasks(page=1, per_page=1000)  # Use a large number to get all tasks
        return tasks

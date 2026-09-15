import datetime
import typing as tp
import uuid
from abc import ABC, abstractmethod

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus


class AbstractTaskRepository(ABC):
    @abstractmethod
    async def find_tasks(  # noqa: PLR0913, PLR0917
        self,
        name: str | None = None,
        status: TaskStatus | None = None,
        start_date: datetime.datetime | None = None,
        end_date: datetime.datetime | None = None,
        sort_by: tp.Literal['started_at', 'finished_at', 'runtime'] | None = None,
        sort_order: tp.Literal['asc', 'desc'] = 'desc',
        limit: int = 30,
        offset: int = 0,
    ) -> list[Task]:
        """
        Retrieve tasks with pagination and filtering.

        Args:
            status: Filter by task status
            name: Filter by task name (fuzzy search)
            start_date: Filter by tasks started at or after this datetime (inclusive)
            end_date: Filter by tasks started at or before this datetime (inclusive)
            sort_by: Column to sort by ('started_at', 'finished_at' or 'runtime')
            sort_order: Sort order ('asc' or 'desc')
            limit: Number of tasks to retrieve
            offset: Number of tasks to skip

        Returns:
            List of tasks matching the criteria.
        """
        ...

    @abstractmethod
    async def get_task_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Retrieve a specific task by ID."""
        ...

    @abstractmethod
    async def create_task(
        self,
        task_id: uuid.UUID,
        task_arguments: QueuedTask,
    ) -> None: ...

    @abstractmethod
    async def update_task(
        self,
        task_id: uuid.UUID,
        task_arguments: StartedTask | ExecutedTask,
    ) -> None: ...

    @abstractmethod
    async def batch_update(
        self,
        old_status: TaskStatus,
        new_status: TaskStatus,
    ) -> None: ...

    @abstractmethod
    async def delete_task(
        self,
        task_id: uuid.UUID,
    ) -> None: ...

    @abstractmethod
    async def delete_tasks(
        self,
        task_ids: list[uuid.UUID],
    ) -> None:
        """
        Delete multiple tasks by their IDs.

        Args:
            task_ids: List of task IDs to delete.
        """
        ...

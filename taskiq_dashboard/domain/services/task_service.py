import typing as tp
import uuid
from abc import ABC, abstractmethod

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus


class TaskRepository(ABC):
    @abstractmethod
    async def find_tasks(  # noqa: PLR0913
        self,
        name: str | None = None,
        status: TaskStatus | None = None,
        sort_by: tp.Literal['started_at', 'finished_at'] | None = None,
        sort_order: tp.Literal['asc', 'desc'] = 'desc',
        limit: int = 30,
        offset: int = 0,
    ) -> list[Task]:
        """
        Retrieve tasks with pagination and filtering.

        Args:
            status: Filter by task status
            name: Filter by task name (fuzzy search)
            sort_by: Column to sort by ('started_at' or 'finished_at')
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

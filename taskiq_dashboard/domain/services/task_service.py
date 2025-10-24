import uuid
from abc import ABC, abstractmethod

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus


class TaskService(ABC):
    @abstractmethod
    async def get_tasks(
        self,
        page: int = 1,
        per_page: int = 30,
        status: TaskStatus | None = None,
        name_search: str | None = None,
    ) -> tuple[list[Task], int]:
        """
        Retrieve tasks with pagination and filtering.

        Args:
            page: The page number (1-indexed)
            per_page: Number of tasks per page
            status: Filter by task status
            name_search: Filter by task name (fuzzy search)

        Returns:
            Tuple of (tasks, total_count)
        """
        ...

    @abstractmethod
    async def get_task_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Retrieve a specific task by ID."""
        ...

    @abstractmethod
    async def create_task(
        self,
        task_id: str,
        task_arguments: QueuedTask,
    ) -> None: ...

    @abstractmethod
    async def update_task(
        self,
        task_id: str,
        task_arguments: StartedTask | ExecutedTask,
    ) -> None: ...

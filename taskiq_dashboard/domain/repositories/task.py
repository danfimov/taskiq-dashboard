import datetime
import typing as tp
import uuid
from abc import ABC, abstractmethod
from collections.abc import Collection

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
        sort_by: str | None = None,
        sort_order: tp.Literal['asc', 'desc'] = 'desc',
        limit: int = 30,
        offset: int = 0,
        finished_start: datetime.datetime | None = None,
        finished_end: datetime.datetime | None = None,
        text_filters: dict[str, str] | None = None,
        label_filters: dict[str, str] | None = None,
        search_fields: Collection[str] | None = None,
    ) -> list[Task]:
        """
        Retrieve tasks with pagination and filtering.

        Args:
            status: Filter by task status
            name: Case-insensitive contains search. Which columns it hits depends on search_fields.
            start_date: Filter by tasks started at or after this datetime (inclusive)
            end_date: Filter by tasks started at or before this datetime (inclusive)
            sort_by: Built-in column name, or a label key when it is not a built-in column
            sort_order: Sort order ('asc' or 'desc')
            limit: Number of tasks to retrieve
            offset: Number of tasks to skip
            finished_start: Filter by tasks finished at or after this datetime (inclusive)
            finished_end: Filter by tasks finished at or before this datetime (inclusive)
            text_filters: Contains filters for built-in text columns, currently worker
            label_filters: Contains filters for task label keys
            search_fields: Columns the name search covers. None searches id and name.

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

import typing as tp
import uuid

import sqlalchemy as sa

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class TaskRepository(AbstractTaskRepository):
    def __init__(
        self, session_provider: AsyncPostgresSessionProvider, task_model: type[PostgresTask] | type[SqliteTask]
    ) -> None:
        self._session_provider = session_provider
        self.task = task_model

    async def find_tasks(  # noqa: PLR0913
        self,
        name: str | None = None,
        status: TaskStatus | None = None,
        sort_by: tp.Literal['started_at', 'finished_at'] | None = None,
        sort_order: tp.Literal['asc', 'desc'] = 'desc',
        limit: int = 30,
        offset: int = 0,
    ) -> list[Task]:
        query = sa.select(self.task)
        if name and len(name) > 1:
            search_pattern = f'%{name.strip()}%'
            query = query.where(self.task.name.ilike(search_pattern))
        if status is not None:
            query = query.where(self.task.status == status.value)
        if sort_by:
            if sort_by == 'finished_at':
                sort_column = self.task.finished_at
            elif sort_by == 'started_at':
                sort_column = self.task.started_at
            else:
                raise ValueError('Unsupported sort_by value: %s', sort_by)
            query = query.order_by(sort_column.asc()) if sort_order == 'asc' else query.order_by(sort_column.desc())
        query = query.limit(limit).offset(offset)
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task_schemas = result.scalars().all()
        return [Task.model_validate(task) for task in task_schemas]

    async def get_task_by_id(self, task_id: uuid.UUID) -> Task | None:
        query = sa.select(self.task).where(self.task.id == task_id)
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task = result.scalar_one_or_none()

        if not task:
            return None

        return Task.model_validate(task)

    async def create_task(
        self,
        task_id: uuid.UUID,
        task_arguments: QueuedTask,
    ) -> None:
        query = sa.insert(self.task).values(
            id=task_id,
            name=task_arguments.task_name,
            status=TaskStatus.QUEUED.value,
            worker=task_arguments.worker or '',
            args=task_arguments.args,
            kwargs=task_arguments.kwargs,
            labels=task_arguments.labels,
            queued_at=task_arguments.queued_at,
        )
        async with self._session_provider.session() as session:
            await session.execute(query)

    async def update_task(
        self,
        task_id: uuid.UUID,
        task_arguments: StartedTask | ExecutedTask,
    ) -> None:
        query = sa.update(self.task).where(self.task.id == task_id)

        if isinstance(task_arguments, StartedTask):
            task_status = TaskStatus.IN_PROGRESS
            query = query.values(
                status=task_status.value,
                started_at=task_arguments.started_at,
                args=task_arguments.args,
                kwargs=task_arguments.kwargs,
                labels=task_arguments.labels,
                name=task_arguments.task_name,
                worker=task_arguments.worker or '',
            )
        else:
            task_status = TaskStatus.FAILURE if task_arguments.error is not None else TaskStatus.COMPLETED
            query = query.values(
                status=task_status.value,
                finished_at=task_arguments.finished_at,
                result=task_arguments.return_value.get('return_value'),
                error=task_arguments.error,
            )
        async with self._session_provider.session() as session:
            await session.execute(query)

    async def batch_update(
        self,
        old_status: TaskStatus,
        new_status: TaskStatus,
    ) -> None:
        query = sa.update(self.task).where(self.task.status == old_status.value).values(status=new_status.value)
        async with self._session_provider.session() as session:
            await session.execute(query)

    async def delete_task(
        self,
        task_id: uuid.UUID,
    ) -> None:
        query = sa.delete(self.task).where(self.task.id == task_id)
        async with self._session_provider.session() as session:
            await session.execute(query)

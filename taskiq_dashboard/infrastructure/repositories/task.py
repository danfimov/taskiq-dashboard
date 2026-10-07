import datetime
import typing as tp
import uuid
from collections.abc import Collection
from contextlib import suppress

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask, Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.repositories import AbstractTaskRepository
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


_DIRECT_SORT_COLUMNS = frozenset({'id', 'name', 'status', 'worker', 'started_at', 'finished_at'})
_MIN_CONTAINS_LENGTH = 1


class TaskRepository(AbstractTaskRepository):
    def __init__(
        self, session_provider: AsyncPostgresSessionProvider, task_model: type[PostgresTask] | type[SqliteTask]
    ) -> None:
        self._session_provider = session_provider
        self.task = task_model

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
        query = self._find_tasks_statement(
            name=name,
            status=status,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
            finished_start=finished_start,
            finished_end=finished_end,
            text_filters=text_filters,
            label_filters=label_filters,
            search_fields=search_fields,
        )
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task_schemas = result.scalars().all()
        return [Task.model_validate(task) for task in task_schemas]

    def _find_tasks_statement(  # noqa: PLR0913, PLR0917
        self,
        name: str | None,
        status: TaskStatus | None,
        start_date: datetime.datetime | None,
        end_date: datetime.datetime | None,
        sort_by: str | None,
        sort_order: tp.Literal['asc', 'desc'],
        limit: int,
        offset: int,
        finished_start: datetime.datetime | None,
        finished_end: datetime.datetime | None,
        text_filters: dict[str, str] | None,
        label_filters: dict[str, str] | None,
        search_fields: Collection[str] | None,
    ) -> sa.Select[tp.Any]:
        query = sa.select(self.task)
        query = self._apply_search(query, name, search_fields)
        if status is not None:
            query = query.where(self.task.status == status.value)
        if start_date is not None:
            query = query.where(self.task.started_at >= start_date)
        if end_date is not None:
            query = query.where(self.task.started_at <= end_date)
        if finished_start is not None:
            query = query.where(self.task.finished_at >= finished_start)
        if finished_end is not None:
            query = query.where(self.task.finished_at <= finished_end)
        for key, value in (text_filters or {}).items():
            if key == 'worker':
                query = _apply_contains(query, self.task.worker, value)
        for key, value in (label_filters or {}).items():
            query = _apply_contains(query, self.task.labels[key].as_string(), value)
        if sort_by:
            sort_column = self._sort_expression(sort_by)
            order_fn = sort_column.asc() if sort_order == 'asc' else sort_column.desc()
            query = query.order_by(order_fn.nulls_last())
        return query.limit(limit).offset(offset)

    def _apply_search(
        self,
        query: sa.Select[tp.Any],
        name: str | None,
        search_fields: Collection[str] | None,
    ) -> sa.Select[tp.Any]:
        if not name or len(name) <= _MIN_CONTAINS_LENGTH:
            return query
        fields = {'id', 'name'} if search_fields is None else set(search_fields)
        search_pattern = f'%{name.strip()}%'
        clauses = []
        if 'name' in fields:
            clauses.append(self.task.name.ilike(search_pattern))
        if 'id' in fields:
            clauses.append(sa.cast(self.task.id, sa.String).ilike(search_pattern))
        if not clauses:
            return query
        return query.where(sa.or_(*clauses))

    def _sort_expression(self, sort_by: str) -> sa.ColumnElement[tp.Any]:
        if sort_by == 'runtime':
            if self.task is PostgresTask:
                return self.task.finished_at - self.task.started_at
            return sa.func.unixepoch(self.task.finished_at) - sa.func.unixepoch(self.task.started_at)
        if sort_by in _DIRECT_SORT_COLUMNS:
            return getattr(self.task, sort_by)
        return self.task.labels[sort_by].as_string()

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
        insert = pg_insert if self.task is PostgresTask else sqlite_insert
        stmt = insert(self.task).values(
            id=task_id,
            name=task_arguments.task_name,
            status=TaskStatus.QUEUED.value,
            worker=task_arguments.worker or '',
            args=task_arguments.args,
            kwargs=task_arguments.kwargs,
            labels=task_arguments.labels,
            queued_at=task_arguments.queued_at,
        )
        upsert_query = stmt.on_conflict_do_update(
            index_elements=[self.task.id],
            set_={
                'queued_at': stmt.excluded.queued_at,
                'worker': stmt.excluded.worker,
                'name': stmt.excluded.name,
                'args': stmt.excluded.args,
                'kwargs': stmt.excluded.kwargs,
                'labels': stmt.excluded.labels,
            },
        )
        async with self._session_provider.session() as session, session.begin():
            await session.execute(upsert_query)

    async def update_task(
        self,
        task_id: uuid.UUID,
        task_arguments: StartedTask | ExecutedTask,
    ) -> None:
        async with self._session_provider.session() as session, session.begin():
            existing_task_query = sa.select(self.task.id).where(self.task.id == task_id)
            result = await session.execute(existing_task_query)
            if result.scalar_one_or_none() is None:
                # other transaction might have created the task, so we can ignore integrity errors here
                with suppress(IntegrityError):
                    async with session.begin_nested():
                        await session.execute(
                            sa.insert(self.task).values(
                                id=task_id,
                                name='unknown',
                                status=TaskStatus.QUEUED.value,
                                worker='unknown',
                                args=[],
                                kwargs={},
                                labels={},
                            )
                        )
            update_query = sa.update(self.task).where(self.task.id == task_id)
            if isinstance(task_arguments, StartedTask):
                task_status = TaskStatus.IN_PROGRESS
                update_query = update_query.values(
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
                update_query = update_query.values(
                    status=task_status.value,
                    finished_at=task_arguments.finished_at,
                    result=task_arguments.return_value.get('return_value'),
                    error=task_arguments.error,
                )
            await session.execute(update_query)

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

    async def delete_tasks(
        self,
        task_ids: list[uuid.UUID],
    ) -> None:
        if not task_ids:
            return
        query = sa.delete(self.task).where(self.task.id.in_(task_ids))
        async with self._session_provider.session() as session:
            await session.execute(query)


def _apply_contains(query: sa.Select[tp.Any], column: tp.Any, value: str) -> sa.Select[tp.Any]:
    stripped = value.strip()
    if len(stripped) <= _MIN_CONTAINS_LENGTH:
        return query
    return query.where(column.ilike(f'%{stripped}%'))

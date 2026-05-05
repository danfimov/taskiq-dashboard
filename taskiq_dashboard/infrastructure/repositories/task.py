import typing as tp
import uuid
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


class TaskRepository(AbstractTaskRepository):
    def __init__(
        self, session_provider: AsyncPostgresSessionProvider, task_model: type[PostgresTask] | type[SqliteTask]
    ) -> None:
        self._session_provider = session_provider
        self.task = task_model

    async def find_task_names(self) -> list[str]:
        query = (
            sa.select(sa.distinct(self.task.name))
            .where(self.task.name.is_not(None))
            .where(self.task.name != '')
            .order_by(self.task.name.asc())
        )
        async with self._session_provider.session() as session:
            rows = (await session.execute(query)).scalars().all()
        return [name for name in rows if isinstance(name, str) and name]

    async def find_tasks(  # noqa: PLR0913
        self,
        name: str | None = None,
        task_name: str | None = None,
        arg_key: str | None = None,
        arg_value: str | None = None,
        status: TaskStatus | None = None,
        sort_by: tp.Literal['started_at', 'finished_at'] | None = None,
        sort_order: tp.Literal['asc', 'desc'] = 'desc',
        limit: int = 30,
        offset: int = 0,
    ) -> list[Task]:
        query = sa.select(self.task)
        if name and len(name) > 1:
            search_pattern = f'%{name.strip()}%'
            id_text = sa.cast(self.task.id, sa.String)
            query = query.where(
                sa.or_(
                    self.task.name.ilike(search_pattern),
                    id_text.ilike(search_pattern)
                )
            )
        normalized_task_name = task_name.strip() if task_name else ''
        if normalized_task_name:
            query = query.where(self.task.name == normalized_task_name)

        normalized_arg_key = arg_key.strip() if arg_key else ''
        normalized_arg_value = arg_value.strip() if arg_value else ''
        if normalized_task_name and normalized_arg_key and normalized_arg_value:
            if self.task is PostgresTask:
                kwargs_condition = self.task.kwargs[normalized_arg_key].astext == normalized_arg_value
            else:
                kwargs_condition = (
                    sa.func.json_extract(self.task.kwargs, f'$.{normalized_arg_key}') == normalized_arg_value
                )
            query = query.where(kwargs_condition)
        if status is not None:
            query = query.where(self.task.status == status.value)
        if sort_by:
            if sort_by == 'finished_at':
                sort_column = self.task.finished_at
            elif sort_by == 'started_at':
                sort_column = self.task.started_at
            else:
                message = f'Unsupported sort_by value: {sort_by}'
                raise ValueError(message)
            query = query.order_by(sort_column.asc()) if sort_order == 'asc' else query.order_by(sort_column.desc())
        query = query.limit(limit).offset(offset)
        async with self._session_provider.session() as session:
            result = await session.execute(query)
            task_schemas = result.scalars().all()
        return [Task.model_validate(task) for task in task_schemas]

    async def find_argument_keys(self, task_name: str | None = None) -> list[str]:
        normalized_task_name = task_name.strip() if task_name else ''
        if not normalized_task_name:
            return []

        if self.task is PostgresTask:
            keys_subquery = (
                sa.select(
                    sa.func.jsonb_object_keys(self.task.kwargs).label('key'),
                )
                .where(self.task.name == normalized_task_name)
                .subquery()
            )
            query = (
                sa.select(sa.distinct(keys_subquery.c.key))
                .where(keys_subquery.c.key.is_not(None))
                .where(keys_subquery.c.key != '')
                .order_by(keys_subquery.c.key.asc())
            )
        else:
            json_each = sa.func.json_each(self.task.kwargs).table_valued('key', 'value').alias('json_each')
            query = (
                sa.select(sa.distinct(json_each.c.key))
                .select_from(self.task)
                .join(json_each, sa.true())
                .where(self.task.name == normalized_task_name)
                .where(json_each.c.key.is_not(None))
                .where(json_each.c.key != '')
                .order_by(json_each.c.key.asc())
            )

        async with self._session_provider.session() as session:
            rows = (await session.execute(query)).scalars().all()

        return [str(key) for key in rows if isinstance(key, str)]

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

import datetime as dt
import uuid

from sqlalchemy.pool import StaticPool

from taskiq_dashboard.domain.dto.task import QueuedTask
from taskiq_dashboard.infrastructure.database.schemas import SqliteTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.repositories.task import TaskRepository
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.settings import ColumnSettings, SqliteSettings


async def test_when_sqlite_storage_filters_and_sorts_worker_and_labels() -> None:
    provider = AsyncPostgresSessionProvider(
        SqliteSettings(file_path=':memory:'),
        engine_parameters={
            'poolclass': StaticPool,
            'connect_args': {'check_same_thread': False},
        },
    )
    settings = ColumnSettings(
        labels={'env': 'Env'},
        visible=['id', 'worker'],
        filterable=['worker', 'env'],
        sortable=['worker', 'env'],
    )
    await SchemaService(provider, table_name='tasks', column_settings=settings).create_schema()
    repository = TaskRepository(session_provider=provider, task_model=SqliteTask)
    now = dt.datetime.now(dt.UTC)
    await repository.create_task(
        uuid.uuid4(),
        QueuedTask(task_name='send', worker='demo_worker', labels={'env': 'prod'}, queued_at=now),
    )
    await repository.create_task(
        uuid.uuid4(),
        QueuedTask(task_name='sync', worker='other_worker', labels={'env': 'staging'}, queued_at=now),
    )

    matched = await repository.find_tasks(text_filters={'worker': 'DEMO'})
    assert [task.worker for task in matched] == ['demo_worker']

    ignored = await repository.find_tasks(text_filters={'worker': 'd'})
    assert len(ignored) == 2

    labeled = await repository.find_tasks(label_filters={'env': 'stag'})
    assert [task.labels['env'] for task in labeled] == ['staging']

    by_worker = await repository.find_tasks(sort_by='worker', sort_order='asc')
    assert [task.worker for task in by_worker] == ['demo_worker', 'other_worker']

    by_label = await repository.find_tasks(sort_by='env', sort_order='asc')
    assert [task.labels['env'] for task in by_label] == ['prod', 'staging']

    await provider.close()

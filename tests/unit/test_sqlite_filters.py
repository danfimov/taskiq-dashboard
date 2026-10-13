import datetime as dt
import uuid

import pytest
from sqlalchemy.pool import StaticPool

from taskiq_dashboard.domain.dto.task import QueuedTask, StartedTask
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


@pytest.fixture
async def repository():
    provider = AsyncPostgresSessionProvider(SqliteSettings(file_path=':memory:'))
    try:
        await SchemaService(provider).create_schema()
        yield TaskRepository(provider, SqliteTask)
    finally:
        await provider.close()


@pytest.mark.parametrize('needle', ['a%', 'a_', 'a/', 'a\\'])
@pytest.mark.parametrize('field', ['name', 'worker', 'env'])
async def test_when_filter_contains_wildcards_or_escape_characters__then_match_literally(repository, field, needle):
    now = dt.datetime.now(dt.UTC)
    for value in (f'prefix{needle}suffix', 'prefixabcsuffix'):
        await repository.create_task(
            uuid.uuid4(), QueuedTask(task_name=value, worker=value, labels={'env': value}, queued_at=now)
        )
    if field == 'name':
        tasks = await repository.find_tasks(name=needle, search_fields={'name'})
    elif field == 'worker':
        tasks = await repository.find_tasks(text_filters={'worker': needle})
    else:
        tasks = await repository.find_tasks(label_filters={'env': needle})
    assert [task.name for task in tasks] == [f'prefix{needle}suffix']


@pytest.mark.parametrize('needle', ['a ', ' a', '  ', '\ta\n'])
async def test_when_trimmed_search_is_too_short__then_ignore_filter(repository, needle):
    now = dt.datetime.now(dt.UTC)
    for name in ('aaa', 'bbb'):
        await repository.create_task(uuid.uuid4(), QueuedTask(task_name=name, worker='same', queued_at=now))
    assert len(await repository.find_tasks(name=needle)) == 2
    assert len(await repository.find_tasks(text_filters={'worker': needle})) == 2


@pytest.mark.parametrize('sort_by', [None, 'worker', 'status', 'env', 'started_at'])
@pytest.mark.parametrize('sort_order', ['asc', 'desc'])
async def test_when_sort_values_tie__then_pages_have_a_stable_id_order(repository, sort_by, sort_order):
    now = dt.datetime.now(dt.UTC)
    for value in (5, 3, 1, 4, 2):
        await repository.create_task(
            uuid.UUID(int=value), QueuedTask(task_name='same', worker='same', labels={'env': 'same'}, queued_at=now)
        )
    ids = []
    for offset in (0, 2, 4):
        tasks = await repository.find_tasks(sort_by=sort_by, sort_order=sort_order, limit=2, offset=offset)
        ids.extend(task.id for task in tasks)
    assert ids == [uuid.UUID(int=value) for value in range(1, 6)]


async def test_when_text_filter_is_unsupported__then_raise_instead_of_ignoring(repository):
    with pytest.raises(ValueError, match='Unsupported text filter columns'):
        await repository.find_tasks(text_filters={'typo': 'value'})


async def test_when_label_key_contains_a_quote__then_filter_and_sort_safely(repository):
    now = dt.datetime.now(dt.UTC)
    key = "env'quote"
    await repository.create_task(
        uuid.uuid4(), QueuedTask(task_name='same', worker='same', labels={key: 'production'}, queued_at=now)
    )
    tasks = await repository.find_tasks(label_filters={key: 'prod'}, sort_by=key)
    assert len(tasks) == 1


@pytest.mark.parametrize('column', ['name', 'worker'])
async def test_when_selecting_a_suggestion__then_match_exactly_instead_of_a_prefix(repository, column):
    now = dt.datetime.now(dt.UTC)
    for value in ('worker-1', 'worker-10', 'x', ' worker-1 '):
        await repository.create_task(uuid.uuid4(), QueuedTask(task_name=value, worker=value, queued_at=now))
    exact = await repository.find_tasks(exact_filters={column: 'worker-1'})
    assert [task.name for task in exact] == ['worker-1']
    contains = await repository.find_tasks(text_filters={column: 'worker-1'})
    assert len(contains) == 3
    assert len(await repository.find_tasks(exact_filters={column: 'x'})) == 1
    whitespace = await repository.find_tasks(exact_filters={column: ' worker-1 '})
    assert [task.name for task in whitespace] == [' worker-1 ']


@pytest.mark.parametrize('column', ['name', 'worker'])
async def test_when_suggesting_values__then_return_recent_distinct_values_and_search_older_tasks(repository, column):
    now = dt.datetime.now(dt.UTC)
    for index in range(25):
        value = f'value-{index:02}'
        await repository.create_task(
            uuid.uuid4(), QueuedTask(task_name=value, worker=value, queued_at=now - dt.timedelta(minutes=index))
        )
    await repository.create_task(
        uuid.uuid4(), QueuedTask(task_name='value-24', worker='value-24', queued_at=now + dt.timedelta(minutes=1))
    )
    recent = await repository.suggest_values(column)
    assert recent == ['value-24', *[f'value-{index:02}' for index in range(19)]]
    assert 'value-22' not in recent
    assert await repository.suggest_values(column, query='value-22') == ['value-22']


@pytest.mark.parametrize('column', ['name', 'worker'])
@pytest.mark.parametrize('needle', ['a%', 'a_', "a'", 'a/'])
async def test_when_searching_suggestions__then_treat_input_as_literal_text(repository, column, needle):
    now = dt.datetime.now(dt.UTC)
    for value in (f'{needle}literal', 'aXliteral'):
        await repository.create_task(uuid.uuid4(), QueuedTask(task_name=value, worker=value, queued_at=now))
    assert await repository.suggest_values(column, query=needle) == [f'{needle}literal']


async def test_when_exact_filter_column_is_unsupported__then_reject_it(repository):
    with pytest.raises(ValueError, match='Unsupported text filter columns'):
        await repository.find_tasks(exact_filters={'status': '1'})


async def test_when_a_task_has_no_queue_timestamp__then_suggestions_use_its_start_timestamp(repository):
    now = dt.datetime.now(dt.UTC)
    await repository.create_task(
        uuid.uuid4(), QueuedTask(task_name='older', worker='older', queued_at=now - dt.timedelta(days=1))
    )
    await repository.update_task(uuid.uuid4(), StartedTask(task_name='newer', worker='newer', started_at=now))
    assert await repository.suggest_values('worker') == ['newer', 'older']

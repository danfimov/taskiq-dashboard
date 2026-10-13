import asyncio
import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.repositories.task import TaskRepository
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.settings import ColumnSettings


_DEFAULT_INDEXES = {
    'ix_taskiq_dashboard__name__trgm',
    'ix_taskiq_dashboard__id__trgm',
    'ix_taskiq_dashboard__status__sort',
    'ix_taskiq_dashboard__started_at__sort',
    'ix_taskiq_dashboard__finished_at__sort',
    'ix_taskiq_dashboard__runtime__sort',
}
_WORKER_INDEXES = {
    'ix_taskiq_dashboard__worker__sort',
    'ix_taskiq_dashboard__worker__trgm',
}
_LABEL_INDEXES = {
    'ix_taskiq_dashboard__label_env__sort',
    'ix_taskiq_dashboard__label_env__trgm',
}


@pytest.fixture
async def index_provider(postgres):
    # Dedicated connections and a private schema allow real concurrent DDL.
    schema = f'indexes_{uuid.uuid4().hex}'
    settings = postgres.model_copy(update={'index_management_dsn': postgres.dsn})
    provider = AsyncPostgresSessionProvider(
        settings, engine_parameters={'connect_args': {'server_settings': {'search_path': f'{schema},public'}}}
    )
    try:
        async with provider.session() as session:
            await session.execute(sa.text(f'CREATE SCHEMA {schema}'))
            await session.execute(sa.text('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public'))
            # Create a local table before checkfirst can discover the public test table.
            await session.execute(sa.schema.CreateTable(PostgresTask.__table__))
        await SchemaService(provider).create_schema()
        yield provider
    finally:
        async with provider.session() as session:
            await session.execute(sa.text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        await provider.close()


async def _index_names(provider):
    async with provider.session() as session:
        result = await session.execute(
            sa.text('SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = :table_name'),
            {'table_name': 'taskiq_dashboard__tasks'},
        )
        return {row[0] for row in result}


async def test_when_index_management_is_disabled__then_startup_creates_no_optional_indexes(index_provider):
    await SchemaService(index_provider).create_schema()
    assert _DEFAULT_INDEXES.isdisjoint(await _index_names(index_provider))


async def test_when_index_endpoint_is_missing__then_skip_optional_ddl(index_provider, postgres, caplog):
    provider = AsyncPostgresSessionProvider(
        postgres,
        engine_parameters={'connect_args': index_provider._engine_parameters['connect_args']},
    )
    try:
        await SchemaService(provider, column_settings=ColumnSettings(manage_indexes=True)).create_schema()
        assert _DEFAULT_INDEXES.isdisjoint(await _index_names(provider))
        assert 'configure postgres.index_management_dsn' in caplog.text
    finally:
        await provider.close()


async def test_when_index_endpoint_is_unreachable__then_startup_continues(index_provider, postgres, caplog):
    unavailable = postgres.model_copy(update={'port': 1})
    settings = postgres.model_copy(update={'index_management_dsn': unavailable.dsn})
    provider = AsyncPostgresSessionProvider(
        settings,
        engine_parameters={'connect_args': index_provider._engine_parameters['connect_args']},
    )
    try:
        await SchemaService(provider, column_settings=ColumnSettings(manage_indexes=True)).create_schema()
        assert _DEFAULT_INDEXES.isdisjoint(await _index_names(provider))
        assert 'continuing startup' in caplog.text
    finally:
        await provider.close()


async def test_when_index_endpoint_is_configured__then_it_uses_a_separate_connection(index_provider, postgres):
    settings = postgres.model_copy(update={'port': 1, 'index_management_dsn': postgres.dsn})
    provider = AsyncPostgresSessionProvider(settings)
    try:
        async with provider.index_management_connection() as connection:
            backend_pid = await connection.scalar(sa.text('SELECT pg_backend_pid()'))
            assert await connection.scalar(sa.text('SELECT current_database()')) == postgres.database
        async with index_provider.session() as session:
            assert (
                await session.scalar(
                    sa.text('SELECT count(*) FROM pg_stat_activity WHERE pid = :pid'),
                    {'pid': backend_pid},
                )
                == 0
            )
    finally:
        await provider.close()


async def test_when_index_management_is_enabled__then_create_indexes_idempotently(index_provider):
    service = SchemaService(index_provider, column_settings=ColumnSettings(manage_indexes=True))
    await service.create_schema()
    names = await _index_names(index_provider)
    assert names >= _DEFAULT_INDEXES
    assert _WORKER_INDEXES.isdisjoint(names)
    await service.create_schema()
    assert await _index_names(index_provider) == names


@pytest.mark.parametrize('key', ['worker', 'env'])
async def test_when_column_is_removed__then_startup_retains_existing_indexes(index_provider, key):
    enabled = ColumnSettings(labels={'env': 'Env'}, filterable=[key], sortable=[key], manage_indexes=True)
    await SchemaService(index_provider, column_settings=enabled).create_schema()
    expected = _WORKER_INDEXES if key == 'worker' else _LABEL_INDEXES
    assert await _index_names(index_provider) >= expected
    await SchemaService(index_provider, column_settings=ColumnSettings(manage_indexes=True)).create_schema()
    assert await _index_names(index_provider) >= expected | _DEFAULT_INDEXES


async def test_when_replicas_start_together__then_indexes_are_created_without_errors(index_provider):
    settings = ColumnSettings(manage_indexes=True)
    await asyncio.gather(*(SchemaService(index_provider, column_settings=settings).create_schema() for _ in range(3)))
    assert await _index_names(index_provider) >= _DEFAULT_INDEXES
    async with index_provider.session() as session:
        invalid = await session.scalars(
            sa.text("""
                SELECT c.relname FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema() AND NOT i.indisvalid
            """),
        )
        assert list(invalid) == []


async def test_when_matching_labels__then_real_and_generic_plans_use_the_expression_index(index_provider):
    settings = ColumnSettings(labels={'env': 'Env'}, filterable=['env'], sortable=['env'], manage_indexes=True)
    async with index_provider.session() as session:
        await session.execute(
            sa.text("""
            INSERT INTO taskiq_dashboard__tasks (id, name, worker, status, args, kwargs, labels)
            SELECT md5(i::text)::uuid, 'task', 'worker', 0, '[]'::jsonb, '{}'::jsonb,
                jsonb_build_object('env', CASE WHEN i % 1000 = 0 THEN 'production' ELSE md5(i::text) END)
            FROM generate_series(1, 20000) AS i
        """)
        )
    await SchemaService(index_provider, column_settings=settings).create_schema()
    async with index_provider.session() as session:
        await session.execute(sa.text('ANALYZE taskiq_dashboard__tasks'))
    repository = TaskRepository(index_provider, PostgresTask)
    query = repository._find_tasks_statement(
        name=None,
        status=None,
        start_date=None,
        end_date=None,
        sort_by=None,
        sort_order='asc',
        limit=30,
        offset=0,
        finished_start=None,
        finished_end=None,
        text_filters=None,
        label_filters={'env': 'production'},
        search_fields=None,
    )
    compiled = query.compile(dialect=PGDialect_asyncpg(), compile_kwargs={'render_postcompile': True})
    assert "'env'" in str(compiled)
    values = [compiled.params[name] for name in compiled.positiontup]
    async with index_provider.autocommit_connection() as connection:
        raw = (await connection.get_raw_connection()).driver_connection
        plan = await raw.fetchval('EXPLAIN (FORMAT JSON) ' + str(compiled), *values)
        assert 'ix_taskiq_dashboard__label_env__trgm' in json.dumps(plan), plan
        await connection.execute(sa.text('SET plan_cache_mode = force_generic_plan'))
        await raw.execute('PREPARE label_filter_plan AS ' + str(compiled))
        literals = ', '.join(str(sa.literal(value).compile(compile_kwargs={'literal_binds': True})) for value in values)
        generic = await raw.fetchval(f'EXPLAIN (FORMAT JSON) EXECUTE label_filter_plan({literals})')
        assert 'ix_taskiq_dashboard__label_env__trgm' in json.dumps(generic), generic
        await raw.execute('DEALLOCATE label_filter_plan')
        await connection.execute(sa.text('RESET plan_cache_mode'))

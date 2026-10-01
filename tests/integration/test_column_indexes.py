import sqlalchemy as sa

from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
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


async def _index_names(session_provider: AsyncPostgresSessionProvider) -> set[str]:
    async with session_provider.session() as session:
        result = await session.execute(
            sa.text('SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = :table_name'),
            {'table_name': 'taskiq_dashboard__tasks'},
        )
        return {row[0] for row in result}


class TestColumnIndexes:
    async def test_when_using_default_config__then_default_indexes_exist_and_worker_indexes_do_not(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        service = SchemaService(session_provider, column_settings=ColumnSettings())
        await service.create_schema()
        names = await _index_names(session_provider)

        assert names >= _DEFAULT_INDEXES
        assert _WORKER_INDEXES.isdisjoint(names)

        await service.create_schema()
        assert await _index_names(session_provider) == names

    async def test_when_worker_is_added_then_removed__then_worker_indexes_follow_the_config(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        enabled = ColumnSettings(
            filterable=['id', 'name', 'status', 'worker', 'started_at'],
            sortable=['worker', 'started_at', 'finished_at', 'runtime'],
        )
        await SchemaService(session_provider, column_settings=enabled).create_schema()
        names = await _index_names(session_provider)
        assert names >= _WORKER_INDEXES
        assert names >= _DEFAULT_INDEXES

        await SchemaService(session_provider, column_settings=ColumnSettings()).create_schema()
        names = await _index_names(session_provider)
        assert _WORKER_INDEXES.isdisjoint(names)
        assert names >= _DEFAULT_INDEXES

    async def test_when_label_column_is_added_then_removed__then_expression_indexes_follow_the_config(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> None:
        enabled = ColumnSettings(
            labels={'env': 'Env'},
            filterable=['id', 'name', 'status', 'started_at', 'env'],
            sortable=['started_at', 'finished_at', 'runtime', 'env'],
        )
        await SchemaService(session_provider, column_settings=enabled).create_schema()
        assert await _index_names(session_provider) >= _LABEL_INDEXES

        await SchemaService(session_provider, column_settings=ColumnSettings()).create_schema()
        names = await _index_names(session_provider)
        assert _LABEL_INDEXES.isdisjoint(names)
        assert names >= _DEFAULT_INDEXES

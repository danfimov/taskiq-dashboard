import logging

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.schema import CreateIndex

from taskiq_dashboard.domain.services import AbstractSchemaService
from taskiq_dashboard.infrastructure.database.indexes import managed_indexes
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask, sa_metadata
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.settings import ColumnSettings


logger = logging.getLogger(__name__)


class SchemaService(AbstractSchemaService):
    def __init__(
        self,
        session_provider: AsyncPostgresSessionProvider,
        table_name: str = 'taskiq_dashboard__tasks',
        column_settings: ColumnSettings | None = None,
    ) -> None:
        self._session_provider = session_provider
        self._column_settings = column_settings or ColumnSettings()
        self._table = SqliteTask if self._session_provider.storage_type == 'sqlite' else PostgresTask
        self._table.__tablename__ = table_name

    async def create_schema(self) -> None:
        async with self._session_provider.session() as session:
            connection = await session.connection()
            await connection.run_sync(sa_metadata.create_all, tables=[self._table.__table__])  # ty: ignore[unresolved-attribute]
        if self._session_provider.storage_type == 'postgres' and self._column_settings.manage_indexes:
            if not self._session_provider.has_index_management_connection:
                logger.warning(
                    'Skipping optional index management: configure postgres.index_management_dsn '
                    'with a direct or session-pooled PostgreSQL endpoint',
                )
                return
            try:
                async with self._session_provider.index_management_connection() as connection:
                    await self._sync_postgres_indexes(connection)
            except Exception:
                logger.warning('Could not manage optional PostgreSQL indexes; continuing startup', exc_info=True)

    async def _sync_postgres_indexes(self, connection: AsyncConnection) -> None:
        table = self._table.__table__  # ty: ignore[unresolved-attribute]
        lock_args = 'hashtext(current_database()), hashtext(current_schema() || :table_name)'
        params = {'table_name': f'taskiq_dashboard_indexes:{table.name}'}
        acquired = await connection.scalar(sa.text(f'SELECT pg_try_advisory_lock({lock_args})'), params)
        if not acquired:
            logger.info('Another replica is managing indexes; skipping index creation')
            return
        try:
            await self._create_postgres_indexes(connection)
        finally:
            await connection.execute(sa.text(f'SELECT pg_advisory_unlock({lock_args})'), params)

    async def _create_postgres_indexes(self, connection: AsyncConnection) -> None:
        table = self._table.__table__  # ty: ignore[unresolved-attribute]
        with managed_indexes(table, self._column_settings) as indexes:
            trgm_available = True
            if any(item.uses_trgm for item in indexes):
                try:
                    await connection.execute(sa.text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
                except DBAPIError:
                    logger.warning('pg_trgm is unavailable; skipping trigram indexes. ILIKE filters still work.')
                    trgm_available = False
            for item in indexes:
                if item.uses_trgm and not trgm_available:
                    continue
                logger.info('Ensuring index %s exists', item.index.name)
                try:
                    await connection.execute(CreateIndex(item.index, if_not_exists=True))
                except DBAPIError:
                    logger.warning('Could not create optional index %s', item.index.name, exc_info=True)

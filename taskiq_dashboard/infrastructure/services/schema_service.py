import logging

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.schema import CreateIndex, DropIndex

from taskiq_dashboard.domain.services import AbstractSchemaService
from taskiq_dashboard.infrastructure.database.indexes import INDEX_PREFIX, managed_indexes
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
            if self._session_provider.storage_type == 'postgres':
                await self._sync_postgres_indexes(connection)

    async def _sync_postgres_indexes(self, connection: AsyncConnection) -> None:
        table = self._table.__table__  # ty: ignore[unresolved-attribute]
        with managed_indexes(table, self._column_settings) as indexes:
            if any(item.uses_trgm for item in indexes):
                await connection.execute(sa.text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
            existing = await self._existing_index_names(connection, table.name)
            desired = {item.index.name: item.index for item in indexes}
            for name, index in desired.items():
                if name in existing:
                    continue
                logger.info('Creating index %s', name)
                await connection.execute(CreateIndex(index))
            for name in existing:
                if name.startswith(INDEX_PREFIX) and name not in desired:
                    logger.info('Dropping index %s', name)
                    await self._drop_index(connection, name)

    async def _existing_index_names(self, connection: AsyncConnection, table_name: str) -> set[str]:
        result = await connection.execute(
            sa.text('SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = :table_name'),
            {'table_name': table_name},
        )
        return {row[0] for row in result}

    async def _drop_index(self, connection: AsyncConnection, name: str) -> None:
        table = self._table.__table__  # ty: ignore[unresolved-attribute]
        transient = sa.Index(name, table.c.id)
        try:
            await connection.execute(DropIndex(transient, if_exists=True))
        finally:
            table = transient.table
            if table is not None and transient in table.indexes:
                table.indexes.remove(transient)

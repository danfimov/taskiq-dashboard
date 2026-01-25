from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask, sa_metadata
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class SchemaService(AbstractSchemaService):
    def __init__(
        self,
        session_provider: AsyncPostgresSessionProvider,
        table_name: str = 'taskiq_dashboard__tasks',
    ) -> None:
        self._session_provider = session_provider
        self._table = SqliteTask if self._session_provider.storage_type == 'sqlite' else PostgresTask
        self._table.__tablename__ = table_name

    async def create_schema(self) -> None:
        async with self._session_provider.session() as session:
            connection = await session.connection()
            await connection.run_sync(sa_metadata.create_all, tables=[self._table.__table__])  # type: ignore[possibly-missing-attribute]

import sqlalchemy as sa

from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class SchemaService(AbstractSchemaService):
    def __init__(
        self,
        session_provider: AsyncPostgresSessionProvider,
        table_name: str = 'taskiq_dashboard__tasks',
    ) -> None:
        self._session_provider = session_provider
        self._table_name = table_name

    async def create_schema(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._table_name} (
            id UUID NOT NULL,
            name TEXT NOT NULL,
            status INTEGER NOT NULL,
            worker TEXT NOT NULL,
            args JSONB NOT NULL DEFAULT '[]',
            kwargs JSONB NOT NULL DEFAULT '{{}}',
            labels JSONB NOT NULL DEFAULT '{{}}',
            result JSONB DEFAULT NULL,
            error TEXT DEFAULT NULL,
            queued_at TIMESTAMP WITH TIME ZONE,
            started_at TIMESTAMP WITH TIME ZONE,
            finished_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT pk_{self._table_name} PRIMARY KEY (id)
        );
        """
        async with self._session_provider.session() as session:
            await session.execute(sa.text(query))

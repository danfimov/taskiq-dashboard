import sqlalchemy as sa

from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider


class SchemaService(AbstractSchemaService):
    def __init__(self, session_provider: AsyncPostgresSessionProvider) -> None:
        self._session_provider = session_provider

    async def create_schema(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID NOT NULL,
            name TEXT NOT NULL,
            status INTEGER NOT NULL,
            worker TEXT NOT NULL,
            args JSONB NOT NULL,
            kwargs JSONB NOT NULL,
            result JSONB,
            error TEXT,
            queued_at TIMESTAMP WITH TIME ZONE NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            finished_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT pk_tasks PRIMARY KEY (id)
        );
        """
        async with self._session_provider.session() as session:
            await session.execute(sa.text(query))

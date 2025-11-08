import typing as tp

from dishka import Provider, Scope, make_async_container, provide

from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository
from taskiq_dashboard.infrastructure import Settings, get_settings
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask, SqliteTask
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.services.schema_service import SchemaService
from taskiq_dashboard.infrastructure.services.task_service import TaskRepository


class TaskiqDashboardProvider(Provider):
    def __init__(self, scope: Scope = Scope.APP) -> None:
        super().__init__(scope=scope)

    @provide
    def provide_settings(self) -> Settings:
        return get_settings()

    @provide
    async def provide_session_provider(
        self,
        settings: Settings,
    ) -> tp.AsyncGenerator[AsyncPostgresSessionProvider, tp.Any]:
        session_provider = AsyncPostgresSessionProvider(
            connection_settings=settings.postgres if settings.storage_type == 'postgres' else settings.sqlite,
        )
        yield session_provider
        await session_provider.close()

    @provide
    def provide_task_service(
        self,
        settings: Settings,
        session_provider: AsyncPostgresSessionProvider,
    ) -> AbstractTaskRepository:
        return TaskRepository(
            session_provider=session_provider,
            task_model=PostgresTask if settings.storage_type == 'postgres' else SqliteTask,
        )

    @provide
    def provide_schema_service(
        self,
        settings: Settings,
        session_provider: AsyncPostgresSessionProvider,
    ) -> AbstractSchemaService:
        return SchemaService(
            session_provider=session_provider,
            table_name='taskiq_dashboard__tasks' if settings.storage_type == 'postgres' else 'tasks',
        )


container = make_async_container(
    TaskiqDashboardProvider(),
)

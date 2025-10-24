import typing as tp

from dishka import Provider, Scope, make_async_container, provide

from taskiq_dashboard.domain.services.task_service import TaskService
from taskiq_dashboard.infrastructure.database.session_provider import AsyncPostgresSessionProvider
from taskiq_dashboard.infrastructure.services.task_service import SqlAlchemyTaskService
from taskiq_dashboard.infrastructure.settings import Settings


class TaskiqDashboardProvider(Provider):
    def __init__(self, scope: Scope = Scope.APP) -> None:
        super().__init__(scope=scope)
        self.settings = Settings()

    @provide
    def provide_settings(self) -> Settings:
        return self.settings

    @provide
    async def provide_session_provider(self) -> tp.AsyncGenerator[AsyncPostgresSessionProvider, tp.Any]:
        session_provider = AsyncPostgresSessionProvider(
            connection_settings=self.settings.postgres,
        )
        yield session_provider
        await session_provider.close()

    @provide
    def provide_task_service(
        self,
        session_provider: AsyncPostgresSessionProvider,
    ) -> TaskService:
        return SqlAlchemyTaskService(
            session_provider=session_provider,
        )


container = make_async_container(
    TaskiqDashboardProvider(),
)

import pathlib

import litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.template.config import TemplateConfig

from taskiq_dashboard.api.handlers.dashboard import DashboardController
from taskiq_dashboard.api.handlers.system import router as system_router
from taskiq_dashboard.infrastructure.database import session_provider
from taskiq_dashboard.infrastructure.settings import Settings
from taskiq_dashboard.domain.services.task_service import TaskService
from taskiq_dashboard.infrastructure.services.task_service import SqlAlchemyTaskService

_settings: Settings | None = None
_session_provider: session_provider.AsyncPostgresSessionProvider | None = None

_task_service: TaskService | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_server() -> litestar.Litestar:
    app = litestar.Litestar(
        route_handlers=[
            system_router,
            DashboardController,
        ],
        template_config=TemplateConfig(
            directory=pathlib.Path("taskiq_dashboard/api/templates"),
            engine=JinjaTemplateEngine,
        ),
        dependencies={
            "session_provider": litestar.di.Provide(get_session_provider),
            "task_service": litestar.di.Provide(get_task_service),
        },
        middleware=[],
        on_startup=[],
        on_shutdown=[],
    )
    return app


def get_session_provider() -> session_provider.AsyncPostgresSessionProvider:
    global _session_provider
    if _session_provider is None:
        settings = get_settings()
        _session_provider = session_provider.AsyncPostgresSessionProvider(
            connection_settings=settings.postgres,
        )
    return _session_provider


def get_task_service(session_provider: session_provider.AsyncPostgresSessionProvider) -> TaskService:
    global _task_service
    if _task_service is None:
        _task_service = SqlAlchemyTaskService(
            session_provider=session_provider,
        )
    return _task_service

import pathlib

import litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.template.config import TemplateConfig
from sqlalchemy.ext.asyncio import AsyncSession

from taskiq_dashboard.api.handlers.dashboard import DashboardController
from taskiq_dashboard.api.handlers.system import router as system_router
from taskiq_dashboard.infrastructure.database import session_provider
from taskiq_dashboard.infrastructure.settings import Settings

_settings: Settings | None = None
_session_provider: session_provider.AsyncPostgresSessionProvider | None = None


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
            "session": litestar.di.Provide(get_session),
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


async def get_session() -> AsyncSession:
    async with get_session_provider().session() as session:
        yield session

import contextlib
import typing as tp
from logging import getLogger

import fastapi
from dishka.integrations.fastapi import setup_dishka
from fastapi.staticfiles import StaticFiles

from taskiq_dashboard import dependencies
from taskiq_dashboard.api.routers import dashboard_router, event_router, system_router
from taskiq_dashboard.api.routers.exception_handlers import exception_handler__not_found
from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService


logger = getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> tp.AsyncGenerator[None, None]:
    schema_service = await app.state.dishka_container.get(AbstractSchemaService)
    await schema_service.create_schema()
    yield
    await app.state.dishka_container.close()


def get_app() -> fastapi.FastAPI:
    docs_path = '/docs'
    app = fastapi.FastAPI(
        title='Taskiq Dashboard',
        summary='Taskiq administration dashboard',
        docs_url=docs_path,
        lifespan=lifespan,
        exception_handlers={
            404: exception_handler__not_found,
        },
    )
    app.include_router(router=system_router)
    app.include_router(router=dashboard_router)
    app.include_router(router=event_router)
    app.mount('/static', StaticFiles(directory='taskiq_dashboard/api/static'), name='static')
    setup_dishka(container=dependencies.container, app=app)

    return app

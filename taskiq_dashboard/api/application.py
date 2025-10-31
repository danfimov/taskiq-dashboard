import contextlib
import typing as tp

import fastapi
from dishka.integrations.fastapi import setup_dishka
from fastapi.staticfiles import StaticFiles

from taskiq_dashboard import dependencies
from taskiq_dashboard.api.middlewares import AccessTokenMiddleware
from taskiq_dashboard.api.routers import action_router, event_router, schedule_router, system_router, task_router
from taskiq_dashboard.api.routers.exception_handlers import exception_handler__not_found
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.domain.services.task_service import TaskRepository


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> tp.AsyncGenerator[None, None]:
    schema_service = await app.state.dishka_container.get(AbstractSchemaService)
    await schema_service.create_schema()

    # we probably missed events about these tasks during the downtime, so we need to mark them as abandoned
    task_repository = await app.state.dishka_container.get(TaskRepository)
    await task_repository.batch_update(
        old_status=TaskStatus.IN_PROGRESS,
        new_status=TaskStatus.ABANDONED,
    )
    await task_repository.batch_update(
        old_status=TaskStatus.QUEUED,
        new_status=TaskStatus.ABANDONED,
    )

    if app.state.broker is not None:
        await app.state.broker.startup()

    if app.state.scheduler is not None:
        for schedule_source in app.state.scheduler.sources:
            await schedule_source.startup()

    yield

    if app.state.scheduler is not None:
        for schedule_source in app.state.scheduler.sources:
            await schedule_source.shutdown()

    if app.state.broker is not None:
        await app.state.broker.shutdown()

    await app.state.dishka_container.close()


def get_application() -> fastapi.FastAPI:
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
    app.include_router(router=task_router)
    app.include_router(router=event_router)
    app.include_router(router=action_router)
    app.include_router(router=schedule_router)
    app.mount('/static', StaticFiles(directory='taskiq_dashboard/api/static'), name='static')
    app.add_middleware(AccessTokenMiddleware)
    setup_dishka(container=dependencies.container, app=app)
    return app

import contextlib
import pathlib
import typing as tp

import fastapi
from dishka.integrations.fastapi import setup_dishka
from fastapi.staticfiles import StaticFiles

from taskiq_dashboard import dependencies
from taskiq_dashboard.api.middlewares import AccessTokenMiddleware
from taskiq_dashboard.api.routers import action_router, event_router, schedule_router, system_router, task_router
from taskiq_dashboard.api.routers.exception_handlers import exception_handler__not_found
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.cleanup_service import AbstractCleanupService
from taskiq_dashboard.domain.services.schema_service import AbstractSchemaService
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository
from taskiq_dashboard.infrastructure import get_settings
from taskiq_dashboard.infrastructure.services.cleanup_service import PeriodicCleanupRunner


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> tp.AsyncGenerator[None, None]:
    schema_service = await app.state.dishka_container.get(AbstractSchemaService)
    await schema_service.create_schema()

    # we probably missed events about these tasks during the downtime, so we need to mark them as abandoned
    task_repository = await app.state.dishka_container.get(AbstractTaskRepository)
    await task_repository.batch_update(
        old_status=TaskStatus.IN_PROGRESS,
        new_status=TaskStatus.ABANDONED,
    )
    await task_repository.batch_update(
        old_status=TaskStatus.QUEUED,
        new_status=TaskStatus.ABANDONED,
    )

    settings = get_settings()
    cleanup_service = await app.state.dishka_container.get(AbstractCleanupService)
    if settings.cleanup.is_enabled and settings.cleanup.is_cleanup_on_startup_enabled:
        await cleanup_service.cleanup()
    cleanup_runner: PeriodicCleanupRunner | None = None
    if settings.cleanup.is_enabled:
        cleanup_runner = PeriodicCleanupRunner(
            cleanup_service=cleanup_service,
            interval_hours=settings.cleanup.periodic_interval_hours,
        )
        await cleanup_runner.start()

    if app.state.broker is not None:
        await app.state.broker.startup()

    if app.state.scheduler is not None:
        for schedule_source in app.state.scheduler.sources:
            await schedule_source.startup()

    yield

    if cleanup_runner:
        await cleanup_runner.stop()

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
    app.mount('/static', StaticFiles(directory=pathlib.Path(__file__).parent / 'static'), name='static')
    app.add_middleware(AccessTokenMiddleware)  # type: ignore[invalid-argument-type]
    setup_dishka(container=dependencies.container, app=app)
    return app

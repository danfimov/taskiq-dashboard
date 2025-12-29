import typing as tp
import uuid
from logging import getLogger

import fastapi
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import RedirectResponse, Response
from starlette import status

from taskiq_dashboard.api.templates import jinja_templates
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository


if tp.TYPE_CHECKING:
    from taskiq import AsyncBroker


router = fastapi.APIRouter(
    prefix='/actions',
    tags=['Action'],
    route_class=dishka_fastapi.DishkaRoute,
)
logger = getLogger(__name__)


@router.post(
    '/run/{task_name}',
    name='Kick task',
)
async def handle_task_run(
    request: fastapi.Request,
    task_name: str,
) -> Response:
    broker: AsyncBroker | None = request.app.state.broker
    if broker is None:
        logger.error('No broker configured to handle task kick', extra={'task_name': task_name})
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'No broker configured')

    task = broker.find_task(task_name)
    if not task:
        logger.error('Task not found in broker', extra={'task_name': task_name})
        return Response(status_code=status.HTTP_404_NOT_FOUND, content=b'Task not found')

    await task.kicker().with_task_id(str(uuid.uuid4())).kiq()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    '/rerun/{task_id}',
    name='Rerun task',
)
async def handle_task_rerun(
    request: fastapi.Request,
    task_id: uuid.UUID,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
) -> Response:
    broker: AsyncBroker | None = request.app.state.broker
    if broker is None:
        logger.error('No broker configured to handle task kick', extra={'task_id': task_id})
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'No broker configured')

    existing_task = await repository.get_task_by_id(task_id)
    if existing_task is None:
        logger.error('Task not found in repository', extra={'task_id': str(task_id)})
        return Response(status_code=status.HTTP_404_NOT_FOUND, content=b'Task not found')
    task = broker.find_task(existing_task.name)
    if not task:
        logger.error('Task not found in broker', extra={'task_name': existing_task.name})
        return Response(status_code=status.HTTP_404_NOT_FOUND, content=b'Task not found')
    new_task_id = str(uuid.uuid4())
    await (
        task.kicker()
        .with_task_id(new_task_id)
        .with_labels(**existing_task.labels)
        .kiq(
            *existing_task.args,
            **existing_task.kwargs,
        )
    )

    return jinja_templates.TemplateResponse(
        'partial/notification.html',
        {
            'request': request,
            'message': (
                f"""
                Task rerun started with ID
                <a class="underline hover:ctp-text-lavander" href="/tasks/{new_task_id}">
                    {new_task_id}.
                </a>
                """
            ),
        },
        status_code=status.HTTP_200_OK,
    )


@router.get(
    '/delete/{task_id}',
    name='Delete task',
)
async def handle_task_delete(
    request: fastapi.Request,
    task_id: uuid.UUID,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
) -> Response:
    await repository.delete_task(task_id)
    mount_prefix = request.url.path.rsplit('/actions/delete/', 1)[0]
    return RedirectResponse(
        url=mount_prefix if mount_prefix else '/',
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )

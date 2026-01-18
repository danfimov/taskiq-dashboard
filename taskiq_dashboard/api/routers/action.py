import typing as tp
import uuid
from logging import getLogger

import fastapi
import pydantic
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


class BulkTaskRequest(pydantic.BaseModel):
    task_ids: list[uuid.UUID]


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


@router.post(
    '/bulk/rerun',
    name='Bulk rerun tasks',
)
async def handle_bulk_task_rerun(
    request: fastapi.Request,
    body: BulkTaskRequest,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
) -> Response:
    broker: AsyncBroker | None = request.app.state.broker
    if broker is None:
        logger.error('No broker configured to handle bulk task rerun')
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'No broker configured')

    if not body.task_ids:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'No task IDs provided')

    rerun_results = []
    errors = []

    for task_id in body.task_ids:
        try:
            existing_task = await repository.get_task_by_id(task_id)
            if existing_task is None:
                errors.append(f'Task {task_id} not found')
                continue

            task = broker.find_task(existing_task.name)
            if not task:
                errors.append(f'Task {existing_task.name} not found in broker')
                continue

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
            rerun_results.append((task_id, new_task_id))
        except Exception as e:
            logger.exception('Error rerunning task', extra={'task_id': str(task_id)})
            errors.append(f'Error rerunning task {task_id}: {str(e)}')

    success_count = len(rerun_results)
    total_count = len(body.task_ids)

    message_parts = [f'Rerun {success_count} of {total_count} tasks.']
    if errors:
        message_parts.append(f'Errors: {len(errors)}')
        for error in errors[:5]:  # Show first 5 errors
            message_parts.append(f'<div class="text-ctp-red">{error}</div>')
        if len(errors) > 5:
            message_parts.append(f'<div>... and {len(errors) - 5} more errors</div>')

    return jinja_templates.TemplateResponse(
        'partial/notification.html',
        {
            'request': request,
            'message': '<br>'.join(message_parts),
        },
        status_code=status.HTTP_200_OK,
    )


@router.post(
    '/bulk/delete',
    name='Bulk delete tasks',
)
async def handle_bulk_task_delete(
    request: fastapi.Request,
    body: BulkTaskRequest,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
) -> Response:
    if not body.task_ids:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'No task IDs provided')
    await repository.delete_tasks(body.task_ids)
    # Return success response - client will reload the page
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )

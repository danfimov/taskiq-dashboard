import typing as tp
import uuid
from logging import getLogger

import fastapi
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import Response
from starlette import status

from taskiq_dashboard.domain.dto.task import ExecutedTask, QueuedTask, StartedTask
from taskiq_dashboard.domain.services.task_service import AbstractTaskRepository


router = fastapi.APIRouter(
    prefix='/api/tasks',
    tags=['Event'],
    route_class=dishka_fastapi.DishkaRoute,
)
logger = getLogger(__name__)


@router.post(
    '/{task_id}/{event}',
    name='Receive task event',
)
async def handle_task_event(
    task_id: uuid.UUID,
    event: tp.Annotated[tp.Literal['queued', 'started', 'executed'], fastapi.Path(title='Event type')],
    task_repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
    body: tp.Annotated[dict[str, tp.Any], fastapi.Body(title='Event data')],
) -> Response:
    """
    Handle task events from TaskiqAdminMiddleware.

    This endpoint receives task events such as 'queued', 'started', and 'executed'
    from the TaskiqAdminMiddleware. It processes the event based on the task ID
    and event type.

    Args:
        task_id: The unique identifier of the task.
        event: The type of event (e.g., 'queued', 'started', 'executed').
    """
    # Here you would implement the logic to handle the task event,
    # such as updating a database record or logging the event.
    task_arguments: QueuedTask | StartedTask | ExecutedTask
    match event:
        case 'queued':
            task_arguments = QueuedTask.model_validate(body)
            await task_repository.create_task(task_id, task_arguments)
            logger.info('Task queued event', extra={'task_id': task_id})
        case 'started':
            task_arguments = StartedTask.model_validate(body)
            await task_repository.update_task(task_id, task_arguments)
            logger.info('Task started event', extra={'task_id': task_id})
        case 'executed':
            task_arguments = ExecutedTask.model_validate(body)
            await task_repository.update_task(task_id, task_arguments)
            logger.info('Task executed event', extra={'task_id': task_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

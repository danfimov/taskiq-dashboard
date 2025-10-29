import json
import typing as tp
import uuid
from urllib.parse import urlencode

import fastapi
import pydantic
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import HTMLResponse

from taskiq_dashboard.api.templates import jinja_templates
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskRepository


router = fastapi.APIRouter(
    prefix='',
    tags=['Tasks'],
    route_class=dishka_fastapi.DishkaRoute,
)


class TaskFilter(pydantic.BaseModel):
    q: str = ''
    status: TaskStatus | None = None
    limit: int = 30
    offset: int = 0
    sort_by: tp.Literal['started_at', 'finished_at'] = 'started_at'
    sort_order: tp.Literal['asc', 'desc'] = 'desc'

    @pydantic.field_validator('status', mode='before')
    @classmethod
    def validate_status(
        cls,
        value: TaskStatus | str | None,
    ) -> TaskStatus | None:
        if isinstance(value, str) and value == 'null':
            return None
        return value  # type: ignore[return-value]

    @pydantic.field_serializer('status', mode='plain')
    def serialize_status(
        self,
        value: TaskStatus | None,
    ) -> str | None:
        if value is None:
            return 'null'
        return str(value.value)

    model_config = pydantic.ConfigDict(
        extra='ignore',
    )


@router.get(
    '/',
    name='Task list view',
    response_class=HTMLResponse,
)
async def search_tasks(
    request: fastapi.Request,
    repository: dishka_fastapi.FromDishka[TaskRepository],
    query: tp.Annotated[TaskFilter, fastapi.Query(...)],
    hx_request: tp.Annotated[bool, fastapi.Header(description='Request from htmx')] = False,  # noqa: FBT002
) -> HTMLResponse:
    tasks = await repository.find_tasks(
        name=query.q,
        status=query.status,
        limit=query.limit,
        offset=query.offset,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )
    headers: dict[str, str] = {}
    template_name = 'home.html'
    if hx_request:
        headers = {
            'HX-Push-Url': '/?' + urlencode(query.model_dump(exclude={'limit', 'offset'})),
        }
        template_name = 'partial/task_list.html'
    return jinja_templates.TemplateResponse(
        template_name,
        {
            'request': request,
            'results': [task.model_dump() for task in tasks],
            **query.model_dump(),
        },
        headers=headers,
    )


@router.get(
    '/tasks/{task_id:uuid}',
    name='Task details view',
    response_class=HTMLResponse,
)
async def task_details(
    request: fastapi.Request,
    repository: dishka_fastapi.FromDishka[TaskRepository],
    task_id: uuid.UUID,
) -> HTMLResponse:
    """
    Display detailed information for a specific task.
    """
    # Get task by ID
    task = await repository.get_task_by_id(task_id)

    if task is None:
        # If task is not found, return 404 page
        return jinja_templates.TemplateResponse(
            name='404.html',
            context={
                'request': request,
                'message': f'Task with ID {task_id} not found',
            },
            status_code=404,
        )

    # Convert task to JSON for the frontend
    task_json = json.dumps(task.model_dump(mode='json'))

    return jinja_templates.TemplateResponse(
        name='task_details.html',
        context={
            'request': request,
            'task': task,
            'task_json': task_json,
            'enable_actions': request.app.state.broker is not None,
            'enable_additional_actions': False,  # Placeholder for future features like retries with different args
        },
    )

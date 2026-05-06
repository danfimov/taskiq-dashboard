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
from taskiq_dashboard.domain.repositories import AbstractTaskRepository


router = fastapi.APIRouter(
    prefix='',
    tags=['Tasks'],
    route_class=dishka_fastapi.DishkaRoute,
)


class TaskFilter(pydantic.BaseModel):
    q: str = ''
    task_name: str = ''
    arg_key: str = ''
    arg_value: str = ''
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
        return value  # ty: ignore[invalid-return-type]

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
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
    query: tp.Annotated[TaskFilter, fastapi.Query(...)],
    hx_request: tp.Annotated[bool, fastapi.Header(description='Request from htmx')] = False,  # noqa: FBT002
) -> HTMLResponse:
    normalized_task_name = query.task_name.strip()
    normalized_arg_value = query.arg_value.strip()
    normalized_arg_key = query.arg_key.strip() if normalized_task_name and normalized_arg_value else ''
    if not normalized_task_name:
        normalized_arg_value = ''
    tasks = await repository.find_tasks(
        name=query.q,
        task_name=normalized_task_name,
        arg_key=normalized_arg_key,
        arg_value=normalized_arg_value,
        status=query.status,
        limit=query.limit,
        offset=query.offset,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )
    keys: list[str] = []
    task_names: list[str] = []
    if not hx_request:
        keys = await repository.find_argument_keys(task_name=normalized_task_name)
        task_names = await repository.find_task_names()

    headers: dict[str, str] = {}
    template_name = 'home.html'
    if hx_request:
        query_params = query.model_dump(exclude={'limit', 'offset'})
        query_params.update(
            {
                'task_name': normalized_task_name,
                'arg_key': normalized_arg_key,
                'arg_value': normalized_arg_value,
            }
        )
        headers = {
            'HX-Push-Url': (
                str(request.url_for('Task list view')) + '?' + urlencode(query_params)
            ),
        }
        template_name = 'partial/task_list.html'
    template_context = query.model_dump()
    template_context.update(
        {
            'task_name': normalized_task_name,
            'arg_key': normalized_arg_key,
            'arg_value': normalized_arg_value,
        }
    )

    return jinja_templates.TemplateResponse(
        request,
        template_name,
        {
            'request': request,
            'results': [task.model_dump() for task in tasks],
            'keys': keys,
            'selected_arg_key': normalized_arg_key,
            'task_names': task_names,
            **template_context,
        },
        headers=headers,
    )


@router.get(
    '/filters/arg-keys',
    name='Task argument key options',
    response_class=HTMLResponse,
)
async def argument_key_options(
    request: fastapi.Request,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
    task_name: str = '',
    arg_key: str = '',
) -> HTMLResponse:
    normalized_task_name = task_name.strip()
    normalized_arg_key = arg_key.strip()
    keys = await repository.find_argument_keys(task_name=normalized_task_name)
    if normalized_arg_key not in keys:
        normalized_arg_key = ''
    return jinja_templates.TemplateResponse(
        request,
        'partial/arg_key_options.html',
        {
            'request': request,
            'keys': keys,
            'selected_arg_key': normalized_arg_key,
        },
    )


@router.get(
    '/tasks/{task_id:uuid}',
    name='Task details view',
    response_class=HTMLResponse,
)
async def task_details(
    request: fastapi.Request,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
    task_id: uuid.UUID,
) -> HTMLResponse:
    """
    Display detailed information for a specific task.
    """
    task = await repository.get_task_by_id(task_id)
    if task is None:
        return jinja_templates.TemplateResponse(
            request,
            name='404.html',
            context={
                'request': request,
                'message': f'Task with ID {task_id} not found',
            },
            status_code=404,
        )
    result_json = None
    if task.result:
        result_json = json.dumps(task.result, indent=2, ensure_ascii=False)
    return jinja_templates.TemplateResponse(
        request,
        name='task_details.html',
        context={
            'request': request,
            'task': task,
            'task_result': result_json,
            'enable_actions': request.app.state.broker is not None,
            'enable_additional_actions': False,  # Placeholder for future features like retries with different args
        },
    )

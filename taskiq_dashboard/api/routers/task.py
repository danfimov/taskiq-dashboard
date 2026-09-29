import datetime
import json
import typing as tp
import uuid

import fastapi
import pydantic
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import HTMLResponse

from taskiq_dashboard.api.columns import (
    FilterControl,
    build_columns,
    build_filter_controls,
    encode_list_query,
    resolve_sort,
)
from taskiq_dashboard.api.templates import jinja_templates
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.repositories import AbstractTaskRepository
from taskiq_dashboard.infrastructure import Settings


router = fastapi.APIRouter(
    prefix='',
    tags=['Tasks'],
    route_class=dishka_fastapi.DishkaRoute,
)


class TaskFilter(pydantic.BaseModel):
    q: str = ''
    status: TaskStatus | None = None
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    finished_start: datetime.datetime | None = None
    finished_end: datetime.datetime | None = None
    limit: int = 30
    offset: int = 0
    sort_by: str = 'started_at'
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

    @pydantic.field_validator('start_date', 'end_date', 'finished_start', 'finished_end', mode='before')
    @classmethod
    def validate_date(
        cls,
        value: datetime.datetime | str | None,
    ) -> datetime.datetime | str | None:
        if isinstance(value, str) and value == '':
            return None
        return value

    @pydantic.field_serializer('status', mode='plain')
    def serialize_status(
        self,
        value: TaskStatus | None,
    ) -> str | None:
        if value is None:
            return 'null'
        return str(value.value)

    @pydantic.field_serializer('start_date', 'end_date', 'finished_start', 'finished_end', mode='plain')
    def serialize_date(
        self,
        value: datetime.datetime | None,
    ) -> str:
        if value is None:
            return ''
        return value.isoformat()

    model_config = pydantic.ConfigDict(
        extra='ignore',
    )


def _form_values(
    query: TaskFilter,
    controls: list[FilterControl],
    text_filters: dict[str, str],
    label_filters: dict[str, str],
    resolved_sort: str | None,
) -> dict[str, str]:
    dumped = query.model_dump()
    values: dict[str, str] = {}
    for control in controls:
        if control.kind == 'search':
            values['q'] = dumped['q']
        elif control.kind == 'status':
            values['status'] = dumped['status']
        elif control.kind == 'datetime':
            values[control.param] = dumped[control.param]
            values[control.end_param] = dumped[control.end_param]
        elif control.kind == 'text':
            if control.param.startswith('label.'):
                values[control.param] = label_filters.get(control.param.removeprefix('label.'), '')
            else:
                values[control.param] = text_filters.get(control.param, '')
    if resolved_sort is not None:
        values['sort_by'] = resolved_sort
        values['sort_order'] = query.sort_order
    return values


def _has_filters(
    query: TaskFilter,
    controls: list[FilterControl],
    text_filters: dict[str, str],
    label_filters: dict[str, str],
) -> bool:
    for control in controls:
        if control.kind == 'search' and len(query.q) > 1:
            return True
        if control.kind == 'status' and query.status is not None:
            return True
        if control.kind == 'datetime' and (
            getattr(query, control.param) is not None or getattr(query, control.end_param) is not None
        ):
            return True
        if control.kind != 'text':
            continue
        raw = (
            label_filters.get(control.param.removeprefix('label.'), '')
            if control.param.startswith('label.')
            else text_filters.get(control.param, '')
        )
        if len(raw.strip()) > 1:
            return True
    return False


@router.get(
    '/',
    name='Task list view',
    response_class=HTMLResponse,
)
async def search_tasks(  # noqa: PLR0913, PLR0917
    request: fastapi.Request,
    repository: dishka_fastapi.FromDishka[AbstractTaskRepository],
    settings: dishka_fastapi.FromDishka[Settings],
    query: tp.Annotated[TaskFilter, fastapi.Query(...)],
    hx_request: tp.Annotated[bool, fastapi.Header(description='Request from htmx')] = False,  # noqa: FBT002
    x_auto_refresh: tp.Annotated[bool, fastapi.Header(description='Background auto-refresh poll')] = False,  # noqa: FBT002
) -> HTMLResponse:
    columns = build_columns(settings.columns)
    controls = build_filter_controls(settings.columns)
    resolved_sort = resolve_sort(query.sort_by, settings.columns)
    search_control = next((control for control in controls if control.kind == 'search'), None)
    status_enabled = any(control.kind == 'status' for control in controls)
    started_enabled = any(control.kind == 'datetime' and control.param == 'start_date' for control in controls)
    finished_enabled = any(control.kind == 'datetime' and control.param == 'finished_start' for control in controls)
    text_filters: dict[str, str] = {}
    label_filters: dict[str, str] = {}
    for control in controls:
        if control.kind != 'text':
            continue
        raw = request.query_params.get(control.param, '')
        if control.param.startswith('label.'):
            label_filters[control.param.removeprefix('label.')] = raw
        else:
            text_filters[control.param] = raw
    tasks = await repository.find_tasks(
        name=query.q if search_control is not None else None,
        status=query.status if status_enabled else None,
        start_date=query.start_date if started_enabled else None,
        end_date=query.end_date if started_enabled else None,
        finished_start=query.finished_start if finished_enabled else None,
        finished_end=query.finished_end if finished_enabled else None,
        text_filters=text_filters,
        label_filters=label_filters,
        search_fields=set(search_control.search_fields) if search_control is not None else set(),
        sort_by=resolved_sort,
        sort_order=query.sort_order,
        limit=query.limit,
        offset=query.offset,
    )
    form_values = _form_values(
        query,
        controls,
        text_filters,
        label_filters,
        resolved_sort,
    )
    headers: dict[str, str] = {}
    template_name = 'home.html'
    if hx_request:
        if not x_auto_refresh:
            headers = {
                'HX-Push-Url': str(request.url_for('Task list view')) + '?' + encode_list_query(form_values),
            }
        template_name = 'partial/task_list.html'

    def list_query(**overrides: object) -> str:
        return encode_list_query(form_values, **overrides)

    return jinja_templates.TemplateResponse(
        request,
        template_name,
        {
            'request': request,
            'results': [task.model_dump() for task in tasks],
            'columns': columns,
            'filter_controls': controls,
            'header_filters': {control.column_key: control for control in controls if control.in_header},
            'filter_values': form_values,
            'has_filters': _has_filters(query, controls, text_filters, label_filters),
            'list_query': list_query,
            **query.model_dump(),
            'sort_by': resolved_sort or '',
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

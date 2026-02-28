import json
import typing as tp
from datetime import datetime
from logging import getLogger
from urllib.parse import urlencode

import fastapi
import pydantic
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import HTMLResponse, Response
from starlette import status
from taskiq import ScheduledTask

from taskiq_dashboard.api.templates import jinja_templates


if tp.TYPE_CHECKING:
    from taskiq import TaskiqScheduler


logger = getLogger(__name__)


router = fastapi.APIRouter(
    prefix='/schedules',
    tags=['Schedule'],
    route_class=dishka_fastapi.DishkaRoute,
)
logger = getLogger(__name__)


class ScheduleFilter(pydantic.BaseModel):
    limit: int = 30
    offset: int = 0


@router.get(
    '/',
    name='Schedule list view',
    response_class=HTMLResponse,
)
async def handle_schedule_list(
    request: fastapi.Request,
    query: tp.Annotated[ScheduleFilter, fastapi.Query(...)],
    hx_request: tp.Annotated[bool, fastapi.Header(description='Request from htmx')] = False,  # noqa: FBT002
) -> HTMLResponse:
    scheduler: TaskiqScheduler | None = request.app.state.scheduler
    if not scheduler:
        return jinja_templates.TemplateResponse(
            name='404.html',
            context={
                'request': request,
                'message': 'Scheduler not configured.',
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )
    schedules = []
    for schedule_source in sorted(scheduler.sources, key=lambda s: id(s)):
        schedules_from_source = [schedule.model_dump() for schedule in await schedule_source.get_schedules()]
        schedules_from_source.sort(key=lambda s: s['schedule_id'])
        for schedule in schedules_from_source:
            schedule['source'] = schedule_source.__class__.__name__
            schedule['source_id'] = id(schedule_source)
        schedules.extend(schedules_from_source)
        if len(schedules) >= query.offset + query.limit:
            break

    headers: dict[str, str] = {}
    template_name = 'schedule_page.html'
    if hx_request:
        template_name = 'partial/schedule_list.html'
        headers = {
            'HX-Push-Url': '/schedules/?' + urlencode(query.model_dump(exclude={'limit', 'offset'})),
        }

    return jinja_templates.TemplateResponse(
        name=template_name,
        context={
            'request': request,
            'schedules': schedules[query.offset :],
            'limit': query.limit,
            'offset': query.offset,
        },
        headers=headers,
        status_code=status.HTTP_200_OK,
    )


@router.get(
    '/{schedule_id}',
    name='Schedule details view',
    response_class=HTMLResponse,
)
async def handle_schedule_details(
    request: fastapi.Request,
    schedule_id: str,
) -> HTMLResponse:
    scheduler: TaskiqScheduler | None = request.app.state.scheduler
    if not scheduler:
        return jinja_templates.TemplateResponse(
            name='404.html',
            context={
                'request': request,
                'message': 'Scheduler not configured.',
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )
    for schedule_source in scheduler.sources:
        for schedule in await schedule_source.get_schedules():
            if schedule.schedule_id == str(schedule_id):
                schedule_dict = schedule.model_dump()
                schedule_dict['source'] = schedule_source.__class__.__name__
                schedule_dict['source_id'] = id(schedule_source)
                return jinja_templates.TemplateResponse(
                    name='schedule_details.html',
                    context={
                        'request': request,
                        'schedule': schedule_dict,
                    },
                    status_code=status.HTTP_200_OK,
                )
    return jinja_templates.TemplateResponse(
        name='404.html',
        context={
            'request': request,
            'message': 'Schedule not found.',
        },
        status_code=status.HTTP_404_NOT_FOUND,
    )


@router.delete(
    '/{schedule_id}',
    name='Delete schedule',
)
async def handle_schedule_delete(
    request: fastapi.Request,
    schedule_id: str,
) -> Response:
    scheduler: TaskiqScheduler | None = request.app.state.scheduler
    if not scheduler:
        return Response(status_code=status.HTTP_400_BAD_REQUEST, content=b'Scheduler not configured.')

    for schedule_source in scheduler.sources:
        for schedule in await schedule_source.get_schedules():
            if schedule.schedule_id != str(schedule_id):
                continue
            try:
                await schedule_source.delete_schedule(schedule_id)
            except NotImplementedError:
                return Response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=b'This schedule source does not support deleting schedules.',
                )
            return Response(
                status_code=status.HTTP_200_OK,
                headers={'HX-Redirect': str(request.url_for('Schedule list view'))},
            )

    logger.warning('Schedule with id %s not found for deletion.', schedule_id)
    return Response(
        status_code=status.HTTP_200_OK,
        headers={'HX-Redirect': str(request.url_for('Schedule list view'))},
    )


def create_error_notification(request: fastapi.Request, message: str) -> Response:
    return jinja_templates.TemplateResponse(
        'partial/notification.html',
        {'request': request, 'message': message, 'level': 'error'},
        status_code=status.HTTP_200_OK,
    )


@router.post(
    '/{schedule_id}',
    name='Edit schedule',
)
async def handle_schedule_edit(  # noqa: PLR0911, PLR0913, C901, PLR0912 Too
    request: fastapi.Request,
    schedule_id: str,
    cron: tp.Annotated[str | None, fastapi.Form()] = None,
    time: tp.Annotated[str | None, fastapi.Form()] = None,
    cron_offset: tp.Annotated[str | None, fastapi.Form()] = None,
    args: tp.Annotated[str, fastapi.Form()] = '[]',
    kwargs: tp.Annotated[str, fastapi.Form()] = '{}',
    labels: tp.Annotated[str, fastapi.Form()] = '{}',
) -> Response:
    scheduler: TaskiqScheduler | None = request.app.state.scheduler
    if not scheduler:
        return create_error_notification(request, 'Scheduler not configured.')

    # Normalize empty strings to None for optional fields
    cron = cron or None
    cron_offset = cron_offset or None
    parsed_time: datetime | None = None
    if time:
        try:
            parsed_time = datetime.fromisoformat(time)
        except ValueError:
            return create_error_notification(request, 'Invalid time format. Expected YYYY-MM-DDTHH:MM.')

    try:
        parsed_args = json.loads(args)
        if not isinstance(parsed_args, list):
            return create_error_notification(request, 'Positional arguments must be a JSON array, e.g. [1, "two"].')
    except json.JSONDecodeError:
        return create_error_notification(request, 'Invalid JSON in "Positional arguments".')
    try:
        parsed_kwargs = json.loads(kwargs)
        if not isinstance(parsed_kwargs, dict):
            return create_error_notification(request, 'Keyword arguments must be a JSON object, e.g. {"key": "value"}.')
    except json.JSONDecodeError:
        return create_error_notification(request, 'Invalid JSON in "Keyword arguments".')
    try:
        parsed_labels = json.loads(labels)
        if not isinstance(parsed_labels, dict):
            return create_error_notification(request, 'Labels must be a JSON object, e.g. {"key": "value"}.')
    except json.JSONDecodeError:
        return create_error_notification(request, 'Invalid JSON in "Labels".')

    for schedule_source in scheduler.sources:
        for schedule in await schedule_source.get_schedules():
            if schedule.schedule_id != str(schedule_id):
                continue

            updated = ScheduledTask(
                task_name=schedule.task_name,
                schedule_id=schedule.schedule_id,
                cron=cron,
                cron_offset=cron_offset,
                time=parsed_time,
                interval=schedule.interval,
                args=parsed_args,
                kwargs=parsed_kwargs,
                labels=parsed_labels,
            )
            try:
                await schedule_source.delete_schedule(schedule_id)
                await schedule_source.add_schedule(updated)
            except NotImplementedError:
                return create_error_notification(request, 'This schedule source does not support editing schedules.')
            return Response(
                status_code=status.HTTP_200_OK,
                headers={'HX-Redirect': str(request.url_for('Schedule details view', schedule_id=schedule_id))},
            )

    return create_error_notification(request, 'Schedule not found.')

import typing as tp
from logging import getLogger
from urllib.parse import urlencode

import fastapi
import pydantic
from dishka.integrations import fastapi as dishka_fastapi
from fastapi.responses import HTMLResponse
from starlette import status

from taskiq_dashboard.api.templates import jinja_templates


if tp.TYPE_CHECKING:
    from taskiq import TaskiqScheduler


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

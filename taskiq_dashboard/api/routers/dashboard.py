import enum
import json
import math
import typing as tp
import uuid

import fastapi
from dishka.integrations import fastapi as dishka_fastapi
from fastapi import Query, Request
from fastapi.responses import HTMLResponse

from taskiq_dashboard.api.templates import jinja_templates
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.services.task_service import TaskService


router = fastapi.APIRouter(
    prefix='',
    tags=['Dashboard'],
    route_class=dishka_fastapi.DishkaRoute,
)


# Create a human-readable status mapping for the UI
class StatusFilter(enum.Enum):
    ALL = 'all'
    IN_PROGRESS = 'in progress'
    COMPLETED = 'completed'
    FAILURE = 'failure'
    QUEUED = 'queued'


# Mapping from StatusFilter to TaskStatus
STATUS_MAPPING = {
    StatusFilter.IN_PROGRESS: TaskStatus.IN_PROGRESS,
    StatusFilter.COMPLETED: TaskStatus.COMPLETED,
    StatusFilter.FAILURE: TaskStatus.FAILURE,
    StatusFilter.QUEUED: TaskStatus.QUEUED,
}


@router.get(
    '/',
    name='Main page',
    response_class=HTMLResponse,
)
async def dashboard_handler(  # noqa: PLR0913
    request: Request,
    task_service: dishka_fastapi.FromDishka[TaskService],
    page: tp.Annotated[int, Query(title='Page number', ge=1)] = 1,
    per_page: tp.Annotated[int, Query(title='Items per page', ge=1, le=100)] = 15,
    status: tp.Annotated[str | None, Query(title='Filter by status')] = None,
    search: tp.Annotated[str | None, Query(title='Search by name')] = None,
    sort_by: tp.Annotated[tp.Literal['started_at', 'finished_at'] | None, Query(title='Sort by column')] = 'started_at',
    sort_order: tp.Annotated[str, Query(title='Sort order')] = 'desc',
) -> HTMLResponse:
    """
    Render dashboard with paginated and filtered tasks.
    """
    # Convert status string to TaskStatus enum if provided
    task_status = None
    if status and status != 'all':
        try:
            status_filter = StatusFilter(status)
            if status_filter != StatusFilter.ALL:
                task_status = STATUS_MAPPING[status_filter]
        except ValueError:
            pass  # Invalid status, ignore the filter

    # Validate sort_by parameter
    if sort_by and sort_by not in ('started_at', 'finished_at'):
        sort_by = None

    # Get filtered and paginated tasks
    tasks, total_count = await task_service.get_tasks(
        page=page,
        per_page=per_page,
        status=task_status,
        name_search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Calculate pagination metadata
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages

    # Determine page numbers to display
    visible_pages = get_visible_page_numbers(page, total_pages)

    # Convert tasks to JSON-serializable format for the frontend
    tasks_json = json.dumps([task.model_dump(mode='json') for task in tasks])

    # Create filter parameters for pagination links
    filter_params = {}
    if status:
        filter_params['status'] = status
    if search:
        filter_params['search'] = search
    if sort_by:
        filter_params['sort_by'] = sort_by
    if sort_order != 'desc':
        filter_params['sort_order'] = sort_order

    # Generate the status options for the dropdown
    status_options = [
        {'value': StatusFilter.ALL.value, 'label': 'All statuses'},
        {'value': StatusFilter.IN_PROGRESS.value, 'label': 'In progress'},
        {'value': StatusFilter.COMPLETED.value, 'label': 'Completed'},
        {'value': StatusFilter.FAILURE.value, 'label': 'Failure'},
        {'value': StatusFilter.QUEUED.value, 'label': 'Queued'},
    ]

    return jinja_templates.TemplateResponse(
        name='dashboard.html',
        context={
            'request': request,
            'tasks': tasks,
            'tasks_json': tasks_json,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_prev': has_prev,
                'has_next': has_next,
                'visible_pages': visible_pages,
                'filter_params': filter_params,
            },
            'filters': {
                'status': status or 'all',
                'search': search or '',
                'status_options': status_options,
            },
            'current_sort': {
                'sort_by': sort_by,
                'sort_order': sort_order,
            },
        },
    )


@router.get(
    '/tasks/{task_id:uuid}',
    name='task_details',
    response_class=HTMLResponse,
)
async def task_details(
    request: Request,
    task_service: dishka_fastapi.FromDishka[TaskService],
    task_id: uuid.UUID,
) -> HTMLResponse:
    """
    Display detailed information for a specific task.
    """
    # Get task by ID
    task = await task_service.get_task_by_id(task_id)

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
        },
    )


def get_visible_page_numbers(current_page: int, total_pages: int, window_size: int = 5) -> list[int]:
    """
    Calculate which page numbers to display in pagination controls.

    Args:
        current_page: The current page number
        total_pages: Total number of pages
        window_size: How many page numbers to show around the current page

    Returns:
        List of page numbers to display
    """
    if total_pages <= window_size + 4:  # Show all pages if there aren't too many
        return list(range(1, total_pages + 1))

    # Always include first and last page
    pages = [1]

    # Calculate window start and end
    window_start = max(2, current_page - window_size // 2)
    window_end = min(total_pages - 1, window_start + window_size - 1)

    # Adjust window start if window end is capped
    if window_end == total_pages - 1:
        window_start = max(2, window_end - window_size + 1)

    # Add ellipsis after first page if necessary
    if window_start > 2:  # noqa: PLR2004
        pages.append(-1)  # -1 represents ellipsis

    # Add window pages
    pages.extend(range(window_start, window_end + 1))

    # Add ellipsis before last page if necessary
    if window_end < total_pages - 1:
        pages.append(-1)  # -1 represents ellipsis

    # Add last page
    pages.append(total_pages)

    return pages

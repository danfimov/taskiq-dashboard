import json
import math
import enum
import typing as tp
import uuid

from litestar import Controller, get
from litestar.di import Provide
from litestar.params import Parameter
from litestar.response import Template
from sqlalchemy.ext.asyncio import AsyncSession

from taskiq_dashboard.infrastructure.services.task_service import SqlAlchemyTaskService
from taskiq_dashboard.domain.services.task_service import TaskService
from taskiq_dashboard.domain.dto.task_status import TaskStatus


def provide_task_service(session: AsyncSession) -> TaskService:
    return SqlAlchemyTaskService(session)


# Create a human-readable status mapping for the UI
class StatusFilter(enum.Enum):
    ALL = "all"
    IN_PROGRESS = "in progress"
    COMPLETED = "completed"
    FAILURE = "failure"
    ABANDONED = "abandoned"


# Mapping from StatusFilter to TaskStatus
STATUS_MAPPING = {
    StatusFilter.IN_PROGRESS: TaskStatus.IN_PROGRESS,
    StatusFilter.COMPLETED: TaskStatus.COMPLETED,
    StatusFilter.FAILURE: TaskStatus.FAILURE,
    StatusFilter.ABANDONED: TaskStatus.ABANDONED,
}


class DashboardController(Controller):
    path = "/dashboard"
    dependencies = {"task_service": Provide(provide_task_service)}

    @get("/", name="dashboard")
    async def dashboard(
        self,
        task_service: TaskService,
        page: int = Parameter(default=1, title="Page number", ge=1),
        per_page: int = Parameter(default=15, title="Items per page", ge=1, le=100),
        status: str | None = Parameter(default=None, title="Filter by status"),
        search: str | None = Parameter(default=None, title="Search by name"),
    ) -> Template:
        """
        Render dashboard with paginated and filtered tasks.
        """
        # Convert status string to TaskStatus enum if provided
        task_status = None
        if status and status != "all":
            try:
                status_filter = StatusFilter(status)
                if status_filter != StatusFilter.ALL:
                    task_status = STATUS_MAPPING[status_filter]
            except ValueError:
                pass  # Invalid status, ignore the filter

        # Get filtered and paginated tasks
        tasks, total_count = await task_service.get_tasks(
            page=page,
            per_page=per_page,
            status=task_status,
            name_search=search,
        )

        # Calculate pagination metadata
        total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
        has_prev = page > 1
        has_next = page < total_pages

        # Determine page numbers to display
        visible_pages = get_visible_page_numbers(page, total_pages)

        # Convert tasks to JSON-serializable format for the frontend
        tasks_json = json.dumps([task.model_dump(mode="json") for task in tasks])

        # Create filter parameters for pagination links
        filter_params = {}
        if status:
            filter_params["status"] = status
        if search:
            filter_params["search"] = search

        # Generate the status options for the dropdown
        status_options = [
            {"value": "all", "label": "All Statuses"},
            {"value": "running", "label": "Running"},
            {"value": "success", "label": "Success"},
            {"value": "error", "label": "Error"},
        ]

        return Template(
            template_name="dashboard.html",
            context={
                "tasks": tasks,
                "tasks_json": tasks_json,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next,
                    "visible_pages": visible_pages,
                    "filter_params": filter_params,
                },
                "filters": {
                    "status": status or "all",
                    "search": search or "",
                    "status_options": status_options,
                }
            }
        )

    @get("/tasks/{task_id:uuid}", name="task_details")
    async def task_details(
        self,
        task_service: TaskService,
        task_id: uuid.UUID,
    ) -> Template:
        """
        Display detailed information for a specific task.
        """
        # Get task by ID
        task = await task_service.get_task_by_id(task_id)

        if task is None:
            # If task is not found, return 404 page
            return Template(
                template_name="404.html",
                context={"message": f"Task with ID {task_id} not found"},
                status_code=404,
            )

        # Convert task to JSON for the frontend
        task_json = json.dumps(task.model_dump(mode="json"))

        return Template(
            template_name="task_details.html",
            context={
                "task": task,
                "task_json": task_json,
            }
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
    if window_start > 2:
        pages.append(-1)  # -1 represents ellipsis

    # Add window pages
    pages.extend(range(window_start, window_end + 1))

    # Add ellipsis before last page if necessary
    if window_end < total_pages - 1:
        pages.append(-1)  # -1 represents ellipsis

    # Add last page
    pages.append(total_pages)

    return pages


def build_query_string(params: dict[str, tp.Any]) -> str:
    """Build a query string from parameters."""
    parts = []
    for key, value in params.items():
        if value is not None and value != "":
            parts.append(f"{key}={value}")

    if not parts:
        return ""

    return "?" + "&".join(parts)

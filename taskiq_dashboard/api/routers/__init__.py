from taskiq_dashboard.api.routers.event import router as event_router
from taskiq_dashboard.api.routers.system import router as system_router
from taskiq_dashboard.api.routers.task import router as task_router


__all__ = [
    'event_router',
    'system_router',
    'task_router',
]

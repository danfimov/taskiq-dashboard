from taskiq_dashboard.api.routers.action import router as action_router
from taskiq_dashboard.api.routers.event import router as event_router
from taskiq_dashboard.api.routers.schedule import router as schedule_router
from taskiq_dashboard.api.routers.system import router as system_router
from taskiq_dashboard.api.routers.task import router as task_router


__all__ = [
    'action_router',
    'event_router',
    'schedule_router',
    'system_router',
    'task_router',
]

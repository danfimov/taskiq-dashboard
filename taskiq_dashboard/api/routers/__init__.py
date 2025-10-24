from taskiq_dashboard.api.routers.dashboard import router as dashboard_router
from taskiq_dashboard.api.routers.event import router as event_router
from taskiq_dashboard.api.routers.system import router as system_router


__all__ = [
    'dashboard_router',
    'event_router',
    'system_router',
]

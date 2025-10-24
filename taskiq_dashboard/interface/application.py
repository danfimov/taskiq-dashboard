import typing as tp

import uvicorn

from taskiq_dashboard.api.application import get_app


class TaskiqDashboard:
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 8000,
        **uvicorn_kwargs: tp.Any,
    ) -> None:
        """Initialize Taskiq Dashboard application.

        Args:
            host: Host to bind the application to.
            port: Port to bind the application to.
            uvicorn_kwargs: Additional keyword arguments to pass to uvicorn.
        """
        self._uvicorn_kwargs = {
            'host': host,
            'port': port,
            'reload': False,
            'workers': 1,
            'lifespan': 'on',
            'proxy_headers': True,
            'forwarded_allow_ips': '*',
            'timeout_keep_alive': 60,
            'access_log': True,
        }
        self._uvicorn_kwargs.update(uvicorn_kwargs or {})

    def run(self) -> None:
        application = get_app()
        uvicorn.run(
            application,
            **self._uvicorn_kwargs,  # type: ignore[arg-type]
        )

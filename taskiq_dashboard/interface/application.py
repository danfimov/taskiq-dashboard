import asyncio
import typing as tp

import uvicorn
from pydantic import SecretStr

from taskiq_dashboard.api.application import get_app
from taskiq_dashboard.dependencies import container
from taskiq_dashboard.infrastructure.settings import Settings


class TaskiqDashboard:
    def __init__(
        self,
        api_token: str = 'supersecret',  # noqa: S107
        host: str = 'localhost',
        port: int = 8000,
        **uvicorn_kwargs: tp.Any,
    ) -> None:
        """Initialize Taskiq Dashboard application.

        Args:
            api_token: Access token for securing the dashboard API.
            host: Host to bind the application to.
            port: Port to bind the application to.
            uvicorn_kwargs: Additional keyword arguments to pass to uvicorn.
        """
        settings = asyncio.run(
            container.get(Settings),
        )
        settings.api.token = SecretStr(api_token)

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

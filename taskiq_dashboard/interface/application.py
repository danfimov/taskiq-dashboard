import typing as tp

import uvicorn
from pydantic import SecretStr

from taskiq_dashboard.api.application import get_application
from taskiq_dashboard.infrastructure import PostgresSettings, get_settings


class TaskiqDashboard:
    def __init__(
        self,
        api_token: str,
        database_dsn: str | None = None,
        **uvicorn_kwargs: tp.Any,
    ) -> None:
        """Initialize Taskiq Dashboard application.

        Args:
            api_token: Access token for securing the dashboard API.
            database_dsn: URL for the database.
            uvicorn_kwargs: Additional keyword arguments to pass to uvicorn.
        """
        self.settings = get_settings()
        self.settings.api.token = SecretStr(api_token)

        if database_dsn:
            self.settings.db = PostgresSettings(dsn=database_dsn)  # type: ignore[call-arg]

        self._uvicorn_kwargs = {
            'host': 'localhost',
            'port': 8000,
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
        application = get_application()
        uvicorn.run(
            application,
            **self._uvicorn_kwargs,  # type: ignore[arg-type]
        )

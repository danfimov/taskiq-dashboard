import typing as tp

import uvicorn
from pydantic import SecretStr
from taskiq import TaskiqScheduler
from taskiq.abc import AsyncBroker

from taskiq_dashboard.api.application import get_application
from taskiq_dashboard.infrastructure import PostgresSettings, SqliteSettings, get_settings


class TaskiqDashboard:
    def __init__(
        self,
        api_token: str,
        storage_type: tp.Literal['sqlite', 'postgres'] = 'sqlite',
        database_dsn: str = 'sqlite+aiosqlite:///taskiq_dashboard.db',
        broker: AsyncBroker | None = None,
        scheduler: TaskiqScheduler | None = None,
        **uvicorn_kwargs: tp.Any,
    ) -> None:
        """Initialize Taskiq Dashboard application.

        Args:
            api_token: Access token for securing the dashboard API.
            storage_type: Type of the storage backend ('sqlite' or 'postgres').
            database_dsn: URL for the database.
            broker: Optional Taskiq broker instance to integrate with the dashboard.
            scheduler: Optional Taskiq scheduler instance to integrate with the dashboard.
            uvicorn_kwargs: Additional keyword arguments to pass to uvicorn.
        """
        self.settings = get_settings()
        self.settings.api.token = SecretStr(api_token)
        self.settings.storage_type = storage_type
        if storage_type == 'sqlite':
            self.settings.sqlite = SqliteSettings(dsn=database_dsn)  # type: ignore[call-arg]
        else:
            self.settings.postgres = PostgresSettings(dsn=database_dsn)  # type: ignore[call-arg]

        self.broker = broker
        self.scheduler = scheduler

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
        self._application = get_application()
        self._application.state.broker = self.broker
        self._application.state.scheduler = self.scheduler

    def run(self) -> None:
        """Run the Taskiq Dashboard application using Uvicorn."""
        uvicorn.run(
            self._application,
            **self._uvicorn_kwargs,  # type: ignore[arg-type]
        )

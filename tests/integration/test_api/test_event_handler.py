import uuid
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urljoin

import pytest
from pydantic import SecretStr
from taskiq import TaskiqMessage
from zapros import AsgiHandler, AsyncClient

from taskiq_dashboard import DashboardMiddleware
from taskiq_dashboard.api.application import get_application
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.infrastructure import get_settings
from taskiq_dashboard.infrastructure.settings import PostgresSettings


class TaskiqAdminWithTestClientMiddleware(DashboardMiddleware):
    """Test middleware where I replace zapros client with test client."""

    def __init__(
        self,
        url: str,
        api_token: str,
        timeout: float = 5,
        broker_name: str = 'default_broker',
        test_client: AsyncClient | None = None,
    ) -> None:
        super().__init__(
            url=url,
            api_token=api_token,
            broker_name=broker_name,
            timeout=timeout,
        )
        self._test_client = test_client

    async def _spawn_request(self, endpoint: str, payload: dict[str, Any]) -> None:
        response = await self._test_client.post(
            urljoin(self.url, endpoint),
            headers={'access-token': self.api_token},
            json=payload,
        )
        assert response.status == 204


@pytest.fixture
async def test_app(database: PostgresSettings) -> AsyncGenerator[AsyncClient]:
    settings = get_settings()
    settings.api.token = SecretStr('test-token')
    async with AsyncClient(handler=AsgiHandler(app=get_application(), startup_timeout=5.0)) as client:
        yield client


@pytest.fixture
async def middleware(test_app: AsyncClient) -> TaskiqAdminWithTestClientMiddleware:
    return TaskiqAdminWithTestClientMiddleware(
        url='http://test',
        api_token='test-token',
        broker_name='test-broker',
        test_client=test_app,
    )


@pytest.mark.integration
class TestAppHandlesMiddlewareRequests:
    async def test_when_post_send_event_send__then_creates_task_with_status_queued(
        self,
        test_app: AsyncClient,
        middleware: TaskiqAdminWithTestClientMiddleware,
        task_service,
    ) -> None:
        # Given
        task_id = uuid.uuid4()
        message = TaskiqMessage(
            task_id=str(task_id),
            task_name='my.process',
            args=[1, 2, 3],
            kwargs={'key': 'value'},
            labels={},
        )
        # When
        await middleware.post_send(message)

        # Then
        task = await task_service.get_task_by_id(task_id)
        assert task is not None
        assert task.name == message.task_name
        assert task.status == TaskStatus.QUEUED
        assert task.args == message.args
        assert task.kwargs == message.kwargs

import asyncio
import json
import re
from collections.abc import AsyncGenerator

import pytest
import zapros
from polyfactory.factories.pydantic_factory import ModelFactory
from taskiq import TaskiqMessage, TaskiqResult
from zapros.matchers import method, path
from zapros.mock import Mock, MockRouter, mock_http

from taskiq_dashboard import DashboardMiddleware


class TaskiqMessageFactory(ModelFactory[TaskiqMessage]):
    __model__ = TaskiqMessage
    __check_model__ = False


@pytest.fixture
async def middleware() -> AsyncGenerator[DashboardMiddleware]:
    middleware = DashboardMiddleware(
        url='http://test_dashboard',
        api_token='supersecret',
        broker_name='my_worker',
    )
    await middleware.startup()
    yield middleware
    await middleware.shutdown()


@pytest.fixture
def zapros_mock() -> AsyncGenerator[MockRouter]:
    with mock_http() as router:
        yield router


def _mock_task_endpoint(router: MockRouter, task_id: str) -> Mock:
    mock = Mock.given(method('POST').and_(path(re.compile(rf'/api/tasks/{task_id}/.*')))).respond(
        zapros.Response(status=200),
    )
    router.add(mock)
    return mock


@pytest.mark.parametrize(
    'method_name',
    ['post_send', 'pre_execute', 'post_execute'],
)
async def test_when_middleware_method_called__then_request_send_with_auth_data(
    zapros_mock: MockRouter,
    middleware: DashboardMiddleware,
    method_name: str,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    mock = _mock_task_endpoint(zapros_mock, message.task_id)

    # when
    if method_name == 'post_send':
        await middleware.post_send(message)
    elif method_name == 'pre_execute':
        await middleware.pre_execute(message)
    elif method_name == 'post_execute':
        await middleware.post_execute(message, result=TaskiqResult(is_err=False, return_value=None, execution_time=1.0))
    await asyncio.gather(*middleware._pending, return_exceptions=True)

    # then
    assert mock.called
    request = mock.calls[0]
    assert request.method == 'POST'
    assert 'access-token' in request.headers
    assert request.headers['access-token'] == 'supersecret'


async def test_when_middleware_shutdown__then_pending_requests_awaited(
    zapros_mock: MockRouter,
    middleware: DashboardMiddleware,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    mock = _mock_task_endpoint(zapros_mock, message.task_id)

    # when
    await middleware.post_send(message)

    # then
    assert len(middleware._pending) > 0, 'Expected pending tasks'
    await asyncio.gather(*middleware._pending, return_exceptions=True)
    assert mock.called
    assert mock.calls[0].method == 'POST'


async def test_when_middleware_startup__then_client_created(
    middleware: DashboardMiddleware,
) -> None:
    # given & when already done in fixture
    # then
    assert middleware._client is not None
    assert isinstance(middleware._client, zapros.AsyncClient)


@pytest.mark.parametrize(
    'parameters',
    [
        pytest.param(
            {'args': [1, 2, 3], 'kwargs': {'key': 'value'}},
            id='simple_args_and_kwargs',
        ),
        pytest.param(
            {'args': ['string', 42, 3.14], 'kwargs': {'list': [1, 2, 3], 'dict': {'nested_key': 'nested_value'}}},
            id='complex_nested_structures',
        ),
        pytest.param(
            {'args': [], 'kwargs': {}},
            id='no_args_or_kwargs',
        ),
        pytest.param(
            {'args': [None, True, False], 'kwargs': {'none_value': None, 'bool_value': True}},
            id='none_and_bool_values',
        ),
    ],
)
async def test_when_basic_parameters_are_passed__then_serialization_works(
    zapros_mock: MockRouter,
    middleware: DashboardMiddleware,
    parameters: dict[str, list | dict],
) -> None:
    # given
    message = TaskiqMessageFactory.build(
        args=parameters['args'],
        kwargs=parameters['kwargs'],
    )
    mock = _mock_task_endpoint(zapros_mock, message.task_id)

    # when
    await middleware.post_send(message)
    await asyncio.gather(*middleware._pending, return_exceptions=True)

    # then
    assert mock.called
    request = mock.calls[0]
    assert request.method == 'POST'

    payload = request.body
    assert b'"args"' in payload
    assert b'"kwargs"' in payload

    json_payload = json.loads(payload)
    assert json_payload['args'] == parameters['args']
    assert json_payload['kwargs'] == parameters['kwargs']

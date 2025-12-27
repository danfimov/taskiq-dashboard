import asyncio
import json
import re
from collections.abc import AsyncGenerator

import httpx
import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from pytest_httpx import HTTPXMock
from taskiq import TaskiqMessage, TaskiqResult

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


@pytest.mark.parametrize(
    'method',
    ['post_send', 'pre_execute', 'post_execute'],
)
async def test_when_middleware_method_called__then_request_send_with_auth_data(
    httpx_mock: HTTPXMock,
    middleware: DashboardMiddleware,
    method: str,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    httpx_mock.add_response(
        method='POST',
        url=re.compile(f'http://test_dashboard/api/tasks/{message.task_id}/.*'),
        status_code=200,
    )

    # when
    if method == 'post_send':
        await middleware.post_send(message)
    elif method == 'pre_execute':
        await middleware.pre_execute(message)
    elif method == 'post_execute':
        await middleware.post_execute(message, result=TaskiqResult(is_err=False, return_value=None, execution_time=1.0))
    await asyncio.gather(*middleware._pending, return_exceptions=True)

    # then
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == 'POST'
    assert 'access-token' in request.headers
    assert request.headers['access-token'] == 'supersecret'


async def test_when_middleware_shutdown__then_pending_requests_awaited(
    httpx_mock: HTTPXMock,
    middleware: DashboardMiddleware,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    httpx_mock.add_response(
        method='POST',
        url=re.compile(f'http://test_dashboard/api/tasks/{message.task_id}/.*'),
        status_code=200,
    )

    # when
    await middleware.post_send(message)

    # then
    assert len(middleware._pending) > 0, 'Expected pending tasks'
    await asyncio.gather(*middleware._pending, return_exceptions=True)
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == 'POST'


async def test_when_middleware_startup__then_client_created(
    middleware: DashboardMiddleware,
) -> None:
    # given & when already done in fixture
    # then
    assert middleware._client is not None
    assert isinstance(middleware._client, httpx.AsyncClient)


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
    httpx_mock: HTTPXMock,
    middleware: DashboardMiddleware,
    parameters: dict[str, list | dict],
) -> None:
    # given
    message = TaskiqMessageFactory.build(
        args=parameters['args'],
        kwargs=parameters['kwargs'],
    )
    httpx_mock.add_response(
        method='POST',
        url=re.compile(f'http://test_dashboard/api/tasks/{message.task_id}/.*'),
        status_code=200,
    )

    # when
    await middleware.post_send(message)
    await asyncio.gather(*middleware._pending, return_exceptions=True)

    # then
    request = httpx_mock.get_request()
    assert request is not None
    assert request.method == 'POST'

    payload = request.content
    assert b'"args"' in payload
    assert b'"kwargs"' in payload

    json_payload = json.loads(payload)
    assert json_payload['args'] == parameters['args']
    assert json_payload['kwargs'] == parameters['kwargs']

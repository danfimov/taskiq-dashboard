import asyncio
import re
from collections.abc import AsyncGenerator

import pytest
import zapros
from polyfactory.factories.pydantic_factory import ModelFactory
from taskiq import TaskiqMessage, TaskiqResult
from zapros import Response
from zapros.matchers import and_
from zapros.mock import (
    HeaderMatcher,
    JsonMatcher,
    Matcher,
    MethodMatcher,
    Mock,
    mock_http,
)

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


class PathRegexpMatcher(Matcher):
    def __init__(self, path: str | re.Pattern[str]) -> None:
        self._path = path

    def match(self, request) -> bool:
        if isinstance(self._path, re.Pattern):
            return self._path.match(request.url.pathname) is not None
        return self._path == request.url.pathname


@pytest.mark.parametrize(
    'taskiq_method',
    ['post_send', 'pre_execute', 'post_execute'],
)
async def test_when_middleware_method_called__then_request_send_with_auth_data(
    middleware: DashboardMiddleware,
    taskiq_method: str,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    with mock_http() as router:
        mocked = (
            Mock.given(
                and_(
                    MethodMatcher('POST'),
                    PathRegexpMatcher(re.compile(f'/api/tasks/{message.task_id}/.*')),
                    HeaderMatcher('access-token', 'supersecret'),
                )
            )
            .respond(Response(status=200))
            .mount(router)
            .once()
        )

        # when
        if taskiq_method == 'post_send':
            await middleware.post_send(message)
        elif taskiq_method == 'pre_execute':
            await middleware.pre_execute(message)
        elif taskiq_method == 'post_execute':
            await middleware.post_execute(
                message, result=TaskiqResult(is_err=False, return_value=None, execution_time=1.0)
            )
        await asyncio.gather(*middleware._pending, return_exceptions=True)

        # then
        mocked.verify()


async def test_when_middleware_shutdown__then_pending_requests_awaited(
    middleware: DashboardMiddleware,
) -> None:
    # given
    message = TaskiqMessageFactory.build()
    with mock_http() as router:
        mocked = (
            Mock.given(
                and_(
                    MethodMatcher('POST'),
                    PathRegexpMatcher(re.compile(f'/api/tasks/{message.task_id}/.*')),
                    HeaderMatcher('access-token', 'supersecret'),
                )
            )
            .respond(Response(status=200))
            .mount(router)
            .once()
        )

        # when
        await middleware.post_send(message)

        # then
        assert len(middleware._pending) > 0, 'Expected pending tasks'
        await asyncio.gather(*middleware._pending, return_exceptions=True)
        mocked.verify()


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
    middleware: DashboardMiddleware,
    parameters: dict[str, list | dict],
) -> None:
    # given
    message = TaskiqMessageFactory.build(
        args=parameters['args'],
        kwargs=parameters['kwargs'],
    )
    with mock_http() as router:
        mocked = (
            Mock.given(
                and_(
                    MethodMatcher('POST'),
                    PathRegexpMatcher(re.compile(f'/api/tasks/{message.task_id}/.*')),
                    HeaderMatcher('access-token', 'supersecret'),
                    JsonMatcher(
                        lambda body: body['args'] == parameters['args'] and body['kwargs'] == parameters['kwargs']
                    ),
                )
            )
            .respond(Response(status=200))
            .mount(router)
            .once()
        )

        # when
        await middleware.post_send(message)
        await asyncio.gather(*middleware._pending, return_exceptions=True)

        # then
        mocked.verify()

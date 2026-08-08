import uuid
from unittest.mock import AsyncMock

import fastapi
import pytest
from starlette.requests import Request

from taskiq_dashboard.api.routers.task import TaskFilter, argument_key_options, router, search_tasks
from taskiq_dashboard.domain.dto.task import Task
from taskiq_dashboard.domain.dto.task_status import TaskStatus


def _make_request(path: str = '/') -> Request:
    app = fastapi.FastAPI()
    app.include_router(router)
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': path,
        'headers': [],
        'query_string': b'',
        'app': app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_when_htmx_list_request_then_skip_metadata_queries_and_normalize_arg_filters() -> None:
    repository = AsyncMock()
    repository.find_tasks.return_value = [
        Task(
            id=uuid.uuid4(),
            name='sample_task',
            status=TaskStatus.COMPLETED,
            worker='worker',
        )
    ]

    response = await search_tasks(
        request=_make_request('/'),
        repository=repository,
        query=TaskFilter(task_name=' sample_task ', arg_key=' entity_id ', arg_value='   '),
        hx_request=True,
    )

    repository.find_tasks.assert_awaited_once_with(
        name='',
        task_name='sample_task',
        arg_key='',
        arg_value='',
        status=None,
        limit=30,
        offset=0,
        sort_by='started_at',
        sort_order='desc',
    )
    repository.find_task_names.assert_not_awaited()
    repository.find_argument_keys.assert_not_awaited()
    expected_url = (
        '/?q=&task_name=sample_task&arg_key=&arg_value=&status=null'
        '&sort_by=started_at&sort_order=desc'
    )
    assert response.headers['HX-Push-Url'] == expected_url


@pytest.mark.asyncio
async def test_when_fetching_arg_keys_and_selected_key_not_available_then_clear_selection() -> None:
    repository = AsyncMock()
    repository.find_argument_keys.return_value = ['entity_id', 'operation']

    response = await argument_key_options(
        request=_make_request('/filters/arg-keys'),
        repository=repository,
        task_name='sample_task',
        arg_key='missing_key',
    )

    repository.find_argument_keys.assert_awaited_once_with(task_name='sample_task')
    assert response.context['keys'] == ['entity_id', 'operation']
    assert response.context['selected_arg_key'] == ''


@pytest.mark.asyncio
async def test_when_htmx_request_has_arg_filters_without_task_name_then_ignore_arg_filters() -> None:
    repository = AsyncMock()
    repository.find_tasks.return_value = []

    await search_tasks(
        request=_make_request('/'),
        repository=repository,
        query=TaskFilter(task_name='  ', arg_key='entity_id', arg_value='A-100'),
        hx_request=True,
    )

    repository.find_tasks.assert_awaited_once_with(
        name='',
        task_name='',
        arg_key='',
        arg_value='',
        status=None,
        limit=30,
        offset=0,
        sort_by='started_at',
        sort_order='desc',
    )

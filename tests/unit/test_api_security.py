import uuid
from collections.abc import AsyncGenerator

import pytest
import zapros
from dishka import make_async_container
from pydantic import SecretStr

from taskiq_dashboard import dependencies
from taskiq_dashboard.api.application import get_application
from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.domain.repositories import AbstractTaskRepository
from taskiq_dashboard.infrastructure import get_settings


@pytest.fixture(params=[('', ''), ('/prefix', ''), ('/prefix', '/prefix')])
def app_path(request) -> tuple[str, str]:
    return request.param


@pytest.fixture
async def test_app(monkeypatch, tmp_path, app_path) -> AsyncGenerator[zapros.AsyncClient]:
    settings = get_settings()
    monkeypatch.setattr(settings.api, 'token', SecretStr('test-token'))
    monkeypatch.setattr(settings, 'storage_type', 'sqlite')
    monkeypatch.setattr(settings.sqlite, 'file_path', str(tmp_path / 'tasks.db'))
    monkeypatch.setattr(settings.cleanup, 'is_enabled', False)
    container = make_async_container(dependencies.TaskiqDashboardProvider())
    monkeypatch.setattr(dependencies, 'container', container)
    app = get_application(root_path=app_path[0])
    app.state.broker = None
    app.state.scheduler = None
    async with zapros.AsyncClient(handler=zapros.AsgiHandler(app=app), base_url='http://test') as client:
        yield client


@pytest.mark.parametrize('event', ['queued', 'started', 'executed'])
@pytest.mark.parametrize(
    ('token', 'expected_status'),
    [(None, 401), ('', 401), ('bad-token', 401), ('test-token', 204)],
)
async def test_event_requires_valid_token(test_app, app_path, event, token, expected_status) -> None:
    task_id = uuid.uuid4()
    endpoint = f'{app_path[1]}/api/tasks/{task_id}'
    payload = {
        'taskName': 'security-test',
        'worker': 'test-worker',
        'queuedAt': '2026-10-01T12:00:00Z',
        'startedAt': '2026-10-01T12:00:01Z',
        'finishedAt': '2026-10-01T12:00:02Z',
        'executionTime': 1.0,
    }
    if event != 'queued':
        response = await test_app.post(
            f'{endpoint}/queued',
            headers={'access-token': 'test-token'},
            json=payload,
        )
        assert response.status == 204

    headers = {} if token is None else {'access-token': token}
    response = await test_app.post(f'{endpoint}/{event}', headers=headers, json=payload)

    assert response.status == expected_status
    if expected_status == 401:
        assert response.json == {'detail': 'Invalid access token'}

    repository = await dependencies.container.get(AbstractTaskRepository)
    task = await repository.get_task_by_id(task_id)
    if expected_status == 401 and event == 'queued':
        assert task is None
    else:
        assert task is not None
        expected_task_status = {
            'queued': TaskStatus.QUEUED,
            'started': TaskStatus.IN_PROGRESS,
            'executed': TaskStatus.COMPLETED,
        }
        assert task.status == (expected_task_status[event] if expected_status == 204 else TaskStatus.QUEUED)


@pytest.mark.parametrize('token', [None, '', 'bad-token'])
async def test_empty_configured_token_rejects_requests(test_app, app_path, monkeypatch, token) -> None:
    monkeypatch.setattr(get_settings().api, 'token', SecretStr(''))
    task_id = uuid.uuid4()
    headers = {} if token is None else {'access-token': token}

    response = await test_app.post(
        f'{app_path[1]}/api/tasks/{task_id}/queued',
        headers=headers,
        json={'taskName': 'security-test', 'worker': 'test-worker', 'queuedAt': '2026-10-01T12:00:00Z'},
    )

    assert response.status == 401
    assert response.json == {'detail': 'Invalid access token'}
    repository = await dependencies.container.get(AbstractTaskRepository)
    assert await repository.get_task_by_id(task_id) is None


async def test_ui_and_health_checks_do_not_require_token(test_app, app_path) -> None:
    for path in ['/', '/liveness', '/readiness']:
        response = await test_app.get(f'{app_path[1]}{path}')
        assert response.status == 200

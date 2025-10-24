"""
How to run:

    1) Run worker in one terminal:
        uv run taskiq worker examples.example_with_schedule_source:broker --workers 1

    2) Run scheduler in another terminal:
        uv run taskiq scheduler examples.example_with_schedule_source:scheduler

    3) Run admin panel in another terminal:
        uv run python -m examples.example_with_schedule_source
"""

import asyncio
import random

from taskiq import TaskiqScheduler
from taskiq.middlewares.taskiq_admin_middleware import TaskiqAdminMiddleware
from taskiq_pg.asyncpg import AsyncpgBroker, AsyncpgResultBackend, AsyncpgScheduleSource

from taskiq_dashboard import TaskiqDashboard


dsn = 'postgres://taskiq_dashboard:look_in_vault@localhost:5432/taskiq_dashboard'
broker = (
    AsyncpgBroker(dsn)
    .with_result_backend(AsyncpgResultBackend(dsn))
    .with_middlewares(
        TaskiqAdminMiddleware(
            url='http://0.0.0.0:8000',  # the url to your taskiq-admin instance
            api_token='supersecret',  # any secret enough string
            taskiq_broker_name='my_worker',
        )
    )
)
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        AsyncpgScheduleSource(
            dsn=dsn,
            broker=broker,
        ),
    ],
)


@broker.task(
    task_name='solve_all_problems',
    schedule=[
        {
            'cron': '*/1 * * * *',  # type: str, either cron or time should be specified.
            'cron_offset': None,  # type: str | timedelta | None, can be omitted.
            'time': None,  # type: datetime | None, either cron or time should be specified.
            'args': [],  # type list[Any] | None, can be omitted.
            'kwargs': {},  # type: dict[str, Any] | None, can be omitted.
            'labels': {},  # type: dict[str, Any] | None, can be omitted.
        },
    ],
)
async def best_task_ever() -> None:
    """Solve all problems in the world."""
    await asyncio.sleep(15)
    print('All problems are solved!')

    error_probability = 0.2
    if random.random() < error_probability:
        raise RuntimeError('An unexpected error occurred while solving problems.')

    return {
        'status': 'success',
        'random_number': random.randint(1, 42),
    }


def run_admin_panel() -> None:
    app = TaskiqDashboard(
        host='0.0.0.0',
        port=8000,
    )
    app.run()


if __name__ == '__main__':
    run_admin_panel()

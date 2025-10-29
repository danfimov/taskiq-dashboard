import asyncio
import random
import typing as tp

from taskiq import TaskiqScheduler
from taskiq.middlewares.taskiq_admin_middleware import TaskiqAdminMiddleware
from taskiq_pg.asyncpg import AsyncpgBroker, AsyncpgResultBackend, AsyncpgScheduleSource

from taskiq_dashboard import TaskiqDashboard


dsn = 'postgres://taskiq-dashboard:look_in_vault@localhost:5432/taskiq-dashboard'
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
    schedule=[{'cron': '*/1 * * * *'}],
)
async def best_task_ever(*args, **kwargs) -> dict[str, tp.Any]:
    """Solve all problems in the world."""
    await asyncio.sleep(15)
    print('All problems are solved!')

    error_probability = 0.2
    if random.random() < error_probability:
        raise RuntimeError('An unexpected error occurred while solving problems.')

    return {
        'status': 'success',
        'random_number': random.randint(1, 42),
        'args': args,
        'kwargs': kwargs,
    }


def run_admin_panel() -> None:
    app = TaskiqDashboard(
        api_token='supersecret',
        broker=broker,
        host='0.0.0.0',
        port=8000,
    )
    app.run()


if __name__ == '__main__':
    run_admin_panel()

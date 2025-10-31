import asyncio
import random
import sys
import typing as tp

from taskiq.middlewares.taskiq_admin_middleware import TaskiqAdminMiddleware
from taskiq_pg.asyncpg import AsyncpgBroker, AsyncpgResultBackend

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


@broker.task(
    task_name='task_in_example_with_broker',
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


async def send_task() -> None:
    """Send a task to the broker."""
    await broker.startup()
    await best_task_ever.kiq('some arg', key='value')
    await broker.shutdown()


if __name__ == '__main__':
    if sys.argv[1] == 'admin_panel':
        print('Starting admin panel...')
        run_admin_panel()
    elif sys.argv[1] == 'send_task':
        print('Sending task to the broker...')
        asyncio.run(send_task())

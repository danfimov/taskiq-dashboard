# taskiq-dashboard

Broker-agnostic admin dashboard for Taskiq

Live demo of UI: https://taskiq-dashboard.danfimov.com/

## Usage

1. Import and connect middleware to your Taskiq broker:

```python
from taskiq.middlewares.taskiq_admin_middleware import TaskiqAdminMiddleware

broker = (
    RedisStreamBroker(
        url=redis_url,
        queue_name="my_lovely_queue",
    )
    .with_result_backend(result_backend)
    .with_middlewares(
        TaskiqAdminMiddleware(
            url="http://localhost:8000", # the url to your taskiq-dashboard instance
            api_token="supersecret",  # secret for accessing the dashboard API
            taskiq_broker_name="my_worker",  # it will be worker name in the dashboard
        )
    )
)
```

2. Run taskiq-dashboard with the following code:

```python
from taskiq_dashboard import TaskiqDashboard


def run_admin_panel() -> None:
    app = TaskiqDashboard(
        api_token='supersecret', # the same secret as in middleware
        database_dsn="postgresql://taskiq-dashboard:look_in_vault@postgres:5432/taskiq-dashboard",
        host='0.0.0.0',
        port=8000,
    )
    app.run()


if __name__ == '__main__':
    run_admin_panel()
```

### Docker compose example

```yaml
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_USER: taskiq-dashboard
      POSTGRES_PASSWORD: look_in_vault
      POSTGRES_DB: taskiq-dashboard
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  dashboard:
    image: ghcr.io/danfimov/taskiq-dashboard:latest
    depends_on:
      - postgres
    environment:
      TASKIQ_DASHBOARD__API__TOKEN: supersecret
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

## Configuration

You can configure the dashboard using environment variables or by passing parameters directly to the `TaskiqDashboard` constructor.

For example you can pass uvicorn parameters like `host`, `port`, `log_level` directly to the constructor:

```python
app = TaskiqDashboard(
    api_token='supersecret',
    database_dsn=...,  # optional
    # all this keywords will be passed to uvicorn
    log_level='info',
    access_log=False,
)
```

You can also configure the database connection using environment variables:

```dotenv
TASKIQ_DASHBOARD__DB__DRIVER=postgresql+asyncpg
TASKIQ_DASHBOARD__DB__HOST=localhost
TASKIQ_DASHBOARD__DB__PORT=5432
TASKIQ_DASHBOARD__DB__USER=taskiq-dashboard
TASKIQ_DASHBOARD__DB__PASSWORD=look_in_vault
TASKIQ_DASHBOARD__DB__DATABASE=taskiq-dashboard
TASKIQ_DASHBOARD__DB__MIN_POOL_SIZE=1
TASKIQ_DASHBOARD__DB__MAX_POOL_SIZE=5
```

## Dashboard

### Task statuses

Let's assume we have a task `do_smth`, there are all states it can embrace:

- `queued` - the task has been sent to the queue without an error
- `running` - the task is grabbed by a worker and is being processed
- `success` - the task is fully processed without any errors
- `failure` - an error occurred during the task processing

## Development

To run the dashboard locally for development, follow these steps:

1. Clone the repository:

```bash
git clone
https://github.com/danfimov/taskiq-dashboard.git
cd taskiq-dashboard
```

2. Create a virtual environment, activate it, install dependencies and pre-commit hooks:

```bash
make init
```

3. Start a local PostgreSQL instance using Docker:

```bash
make run_infra
```

4. Run tailwindcss in watch mode to compile CSS:

```bash
pnpm run dev
```

5. Start the dashboard application:

```bash
make run
```

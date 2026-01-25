---
title: Overview
---

Broker-agnostic admin dashboard for Taskiq.

Live demo of UI: [https://taskiq-dashboard.danfimov.com/](https://taskiq-dashboard.danfimov.com/)

## Installation

To install `taskiq-dashboard` package, run the following command:

=== "pip"

    ```bash
    pip install taskiq-dashboard
    ```

=== "poetry"

    ```bash
    poetry add taskiq-dashboard
    ```

=== "uv"

    ```bash
    uv pip install taskiq-dashboard
    ```

To pull the Docker image with `taskiq-dashboard` application , run the following command:

```bash
docker pull ghcr.io/danfimov/taskiq-dashboard:latest
```

## Usage

### Run with code

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

    === "postgres"

        ```python
        from taskiq_dashboard import TaskiqDashboard
        from your_project.broker import broker  # your Taskiq broker instance

        def run_admin_panel() -> None:
            app = TaskiqDashboard(
                api_token='supersecret', # the same secret as in middleware
                storage_type='postgres',
                database_dsn="postgresql://taskiq-dashboard:look_in_vault@postgres:5432/taskiq-dashboard",
                broker=broker,  # pass your broker instance here to enable additional features
                host='0.0.0.0',
                port=8000,
            )
            app.run()

        if __name__ == '__main__':
            run_admin_panel()
        ```

    === "sqlite"

        ```python
        from taskiq_dashboard import TaskiqDashboard
        from your_project.broker import broker  # your Taskiq broker instance

        def run_admin_panel() -> None:
            app = TaskiqDashboard(
                api_token='supersecret', # the same secret as in middleware
                storage_type='sqlite',
                database_dsn="sqlite+aiosqlite:///taskiq_dashboard.db",
                broker=broker,  # pass your broker instance here to enable additional features
                host='0.0.0.0',
                port=8000,
            )
            app.run()

        if __name__ == '__main__':
            run_admin_panel()
        ```

You can also pass `broker` or `scheduler` instances directly to the `TaskiqDashboard` constructor and get additional features like actions with tasks or schedule configuration. Read more about it in the [tutorial](./tutorial/run_with_broker.md) section.

!!! note "Dashboard can be a part of your existing API server"

    If you already have an API server running, you can mount admin panel routes to it:

    ```python
    from taskiq_dashboard import TaskiqDashboard
    import fastapi

    app = fastapi.FastAPI(...)
    admin_dashboard = TaskiqDashboard(...)
    app.mount('/admin', admin_dashboard.application)
    ```

### Run with docker compose

=== "postgres"

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
          TASKIQ_DASHBOARD__STORAGE_TYPE: postgres
          TASKIQ_DASHBOARD__POSTGRES__HOST: postgres
          TASKIQ_DASHBOARD__API__TOKEN: supersecret
        ports:
          - "8000:8000"

    volumes:
      postgres_data:
    ```

=== "sqlite"

    ```yaml
    services:
      dashboard:
        image: ghcr.io/danfimov/taskiq-dashboard:latest
        environment:
          TASKIQ_DASHBOARD__STORAGE_TYPE: postgres
          TASKIQ_DASHBOARD__SQLITE__DSN: sqlite+aiosqlite:///taskiq_dashboard.db
          TASKIQ_DASHBOARD__API__TOKEN: supersecret
        volumes:
          - taskiq_dashboard_sqlite:/app/taskiq-dashboard.db
        ports:
          - "8000:8000"

    volumes:
      taskiq_dashboard_sqlite:
    ```

## Configuration

Taskiq-dashboard can run with PostgreSQL or SQLite as storage for information about tasks.

You can configure application using environment variables (if you run it inside docker container) or by passing parameters directly to the `TaskiqDashboard` constructor.

For example you can pass uvicorn parameters like `host`, `port`, `log_level` directly to the constructor:

=== "postgres"

    ```python
    app = TaskiqDashboard(
        api_token='supersecret',
        storage_type='postgres',
        database_dsn="postgresql://taskiq-dashboard:look_in_vault@postgres:5432/taskiq-dashboard",
        # all this keywords will be passed to uvicorn
        host='localhost',
        port=8000,
        log_level='info',
        access_log=False,
    )
    ```

=== "sqlite"

    ```python
    app = TaskiqDashboard(
        api_token='supersecret',
        storage_type='sqlite',
        database_dsn="sqlite+aiosqlite:///taskiq_dashboard.db",
        # all this keywords will be passed to uvicorn
        host='localhost',
        port=8000,
        log_level='info',
        access_log=False,
    )
    ```

You can also configure the database connection or API parameters using environment variables:

=== "postgres"

    ```dotenv
    TASKIQ_DASHBOARD__POSTGRES__DRIVER=postgresql+asyncpg
    TASKIQ_DASHBOARD__POSTGRES__HOST=localhost
    TASKIQ_DASHBOARD__POSTGRES__PORT=5432
    TASKIQ_DASHBOARD__POSTGRES__USER=taskiq-dashboard
    TASKIQ_DASHBOARD__POSTGRES__PASSWORD=look_in_vault
    TASKIQ_DASHBOARD__POSTGRES__DATABASE=taskiq-dashboard
    TASKIQ_DASHBOARD__POSTGRES__MIN_POOL_SIZE=1
    TASKIQ_DASHBOARD__POSTGRES__MAX_POOL_SIZE=5
    # or just use DSN: TASKIQ_DASHBOARD__POSTGRES__DSN=postgresql+asyncpg://taskiq-dashboard:look_in_vault@localhost:5432/taskiq-dashboard

    TASKIQ_DASHBOARD__API__HOST=localhost
    TASKIQ_DASHBOARD__API__PORT=8000
    TASKIQ_DASHBOARD__API__TOKEN=supersecret
    ```

=== "sqlite"

    ```dotenv
    TASKIQ_DASHBOARD__SQLITE__DRIVER=sqlite+aiosqlite
    TASKIQ_DASHBOARD__SQLITE__FILE_PATH=taskiq-dashboard.db
    # or just use DSN: TASKIQ_DASHBOARD__SQLITE__DSN=sqlite+aiosqlite:///taskiq_dashboard.db

    TASKIQ_DASHBOARD__API__HOST=localhost
    TASKIQ_DASHBOARD__API__PORT=8000
    TASKIQ_DASHBOARD__API__TOKEN=supersecret
    ```


## Dashboard information

### Task statuses

Let's assume we have a task `do_smth`, there are all states it can embrace:

- `queued` - the task has been sent to the queue without an error;
- `running` - the task is grabbed by a worker and is being processed;
- `success` - the task is fully processed without any errors;
- `failure` - an error occurred during the task processing;
- `abandoned` - taskiq dashboard was shut down while the task was still in `queued` or `running` state, so it probably missed an event on task success/failure.

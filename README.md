# taskiq-dashboard

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/taskiq-dashboard?style=for-the-badge&logo=python)](https://pypi.org/project/taskiq-dashboard/)
[![PyPI](https://img.shields.io/pypi/v/taskiq-dashboard?style=for-the-badge&logo=pypi)](https://pypi.org/project/taskiq-dashboard/)
[![Checks](https://img.shields.io/github/check-runs/danfimov/taskiq-dashboard/main?nameFilter=Tests%20(3.12)&style=for-the-badge)](https://github.com/danfimov/taskiq-dashboard)

Broker-agnostic admin dashboard for Taskiq.

Live demo of UI: [https://taskiq-dashboard.danfimov.com/](https://taskiq-dashboard.danfimov.com/)

## Installation

To install `taskiq-dashboard` package, run the following command:

```bash
pip install taskiq-dashboard
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

    ```python
    from taskiq_dashboard import TaskiqDashboard
    from your_project.broker import broker  # your Taskiq broker instance


    def run_admin_panel() -> None:
        app = TaskiqDashboard(
            api_token='supersecret', # the same secret as in middleware
            storage_type='postgresql',  # or 'sqlite'
            database_dsn="postgresql://taskiq-dashboard:look_in_vault@postgres:5432/taskiq-dashboard",
            broker=broker,  # pass your broker instance here to enable additional features (optional)
            host='0.0.0.0',
            port=8000,
        )
        app.run()


    if __name__ == '__main__':
        run_admin_panel()
    ```

### Run inside docker container

You can use this `docker-compose.yml` file to run `taskiq-dashboard` along with PostgreSQL:

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

You can also run `taskiq-dashboard` with SQLite by using the following `docker-compose.yml` file:

```yaml
services:
  dashboard:
    image: ghcr.io/danfimov/taskiq-dashboard:latest
    environment:
      TASKIQ_DASHBOARD__STORAGE_TYPE: sqlite
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

Taskiq-dashboard can run with PostgreSQL or SQLite.

You can configure it using environment variables or by passing parameters directly to the `TaskiqDashboard` class. For a full list of configuration options, please refer to the [Configuration article](https://danfimov.github.io/taskiq-dashboard/#configuration) in documentation.

## Development

For development and contributing instructions, please refer to the [Contribution guide](https://danfimov.github.io/taskiq-dashboard/contributing/) in documentation.

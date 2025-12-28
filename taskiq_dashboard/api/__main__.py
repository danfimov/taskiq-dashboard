from taskiq_dashboard import TaskiqDashboard
from taskiq_dashboard.infrastructure import get_settings


if __name__ == '__main__':
    settings = get_settings()
    storage_type = settings.storage_type
    TaskiqDashboard(
        api_token=settings.api.token.get_secret_value(),
        storage_type=storage_type,
        database_dsn=(
            settings.postgres.dsn.get_secret_value() if storage_type == 'postgres'
            else settings.sqlite.dsn.get_secret_value()
        ),
        **settings.api.model_dump(exclude='token'),  # type: ignore[arg-type]
    ).run()

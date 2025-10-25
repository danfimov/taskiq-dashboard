from taskiq_dashboard import TaskiqDashboard
from taskiq_dashboard.infrastructure import get_settings


if __name__ == '__main__':
    settings = get_settings()
    if settings.storage_type == 'sqlite':
        database_dsn = settings.sqlite.dsn.get_secret_value()
    else:
        database_dsn = settings.postgres.dsn.get_secret_value()
    TaskiqDashboard(
        api_token=settings.api.token.get_secret_value(),
        database_dsn=database_dsn,
        **settings.api.model_dump(exclude='token'),  # type: ignore[arg-type]
    ).run()

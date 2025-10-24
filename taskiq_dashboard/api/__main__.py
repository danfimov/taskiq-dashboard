from logging import getLogger

from taskiq_dashboard import TaskiqDashboard
from taskiq_dashboard.infrastructure import get_settings


logger = getLogger(__name__)


if __name__ == '__main__':
    settings = get_settings()
    TaskiqDashboard(
        api_token=settings.api.token.get_secret_value(),
        database_dsn=settings.db.dsn.get_secret_value(),
        host=settings.api.host,
        port=settings.api.port,
    ).run()

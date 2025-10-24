from logging import getLogger

from taskiq_dashboard import TaskiqDashboard


logger = getLogger(__name__)


if __name__ == '__main__':
    TaskiqDashboard(
        host='0.0.0.0',  # noqa: S104
        port=8000,
    ).run()

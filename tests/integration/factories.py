from polyfactory import Use
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask


class PostgresTaskFactory(SQLAlchemyFactory[PostgresTask]):
    __check_model__ = True
    __set_relationships__ = False

    status = Use(SQLAlchemyFactory.__random__.choice, [task_status.value for task_status in TaskStatus])
    args = Use(list)

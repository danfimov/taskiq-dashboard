import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, as_declarative, mapped_column

from taskiq_dashboard.domain.dto import task_status


sa_metadata = sa.MetaData(
    naming_convention={
        'ix': 'ix_%(column_0_label)s',
        'uq': 'uq_%(table_name)s_%(column_0_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    },
)


@as_declarative(metadata=sa_metadata)
class BaseTableSchema:
    pass


class Task(BaseTableSchema):
    __tablename__ = 'tasks'

    id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(postgresql.TEXT, nullable=False)
    status: Mapped[task_status.TaskStatus] = mapped_column(sa.Integer, nullable=False)

    worker: Mapped[str] = mapped_column(postgresql.TEXT, nullable=False)

    args: Mapped[str] = mapped_column(postgresql.JSONB, default='')
    kwargs: Mapped[str] = mapped_column(postgresql.JSONB, default='')

    result: Mapped[str] = mapped_column(postgresql.JSONB, nullable=True, default=None)
    error: Mapped[str] = mapped_column(postgresql.TEXT, nullable=True, default=None)

    queued_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=dt.datetime.now,
    )
    started_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=dt.datetime.now,
    )
    finished_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

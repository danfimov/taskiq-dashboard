import datetime
import typing as tp
import uuid

import pydantic

from taskiq_dashboard.domain.dto import task_status


class Task(pydantic.BaseModel):
    id: uuid.UUID
    name: str
    status: task_status.TaskStatus

    worker: str

    args: tp.Any = pydantic.Field(default="")
    kwargs: tp.Any = pydantic.Field(default="")

    result: pydantic.Json | None = None
    error: str | None = None

    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None

    class Config:
        from_attributes = True

import datetime
import typing as tp
import uuid

import pydantic
from pydantic.alias_generators import to_camel

from taskiq_dashboard.domain.dto import task_status


class Task(pydantic.BaseModel):
    id: uuid.UUID
    name: str
    status: task_status.TaskStatus

    worker: str

    args: tp.Any = pydantic.Field(default='')
    kwargs: tp.Any = pydantic.Field(default='')

    result: dict | pydantic.Json | None = None
    error: str | None = None

    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None

    class Config:
        from_attributes = True


class QueuedTask(pydantic.BaseModel):
    args: list[str]
    kwargs: dict[str, str]
    task_name: str
    worker: str
    queued_at: datetime.datetime

    model_config = pydantic.ConfigDict(
        alias_generator=lambda field_name: to_camel(field_name),
        validate_by_alias=True,
        validate_by_name=True,
    )


class StartedTask(pydantic.BaseModel):
    args: list[str]
    kwargs: dict[str, str]
    task_name: str
    worker: str
    started_at: datetime.datetime

    model_config = pydantic.ConfigDict(
        alias_generator=lambda field_name: to_camel(field_name),
        validate_by_alias=True,
        validate_by_name=True,
    )


class ExecutedTask(pydantic.BaseModel):
    finished_at: datetime.datetime
    execution_time: float
    error: str | None = None
    return_value: dict[str, tp.Any] = pydantic.Field(default_factory=dict)

    model_config = pydantic.ConfigDict(
        alias_generator=lambda field_name: to_camel(field_name),
        validate_by_alias=True,
        validate_by_name=True,
    )

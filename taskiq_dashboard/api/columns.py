import logging
import typing as tp

import pydantic

from taskiq_dashboard.infrastructure.settings import ColumnSettings


logger = logging.getLogger(__name__)

BUILTIN_COLUMN_TITLES: dict[str, str] = {
    'id': 'Task ID',
    'name': 'Name',
    'status': 'Status',
    'worker': 'Worker',
    'started_at': 'Started At',
    'finished_at': 'Finished At',
}

SORTABLE_COLUMNS = {'started_at', 'finished_at'}


class Column(pydantic.BaseModel):
    key: str
    title: str
    kind: tp.Literal['builtin', 'label']
    sortable: bool = False


def build_columns(settings: ColumnSettings) -> list[Column]:
    columns = []
    for key in settings.visible:
        title = BUILTIN_COLUMN_TITLES.get(key)
        if title is None:
            logger.warning('Unknown column %r in columns.visible, skipping it', key)
            continue
        columns.append(Column(key=key, title=title, kind='builtin', sortable=key in SORTABLE_COLUMNS))

    columns.extend(
        Column(key=key, title=title, kind='label', sortable=False) for key, title in settings.labels.items()
    )

    return columns

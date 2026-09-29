import logging
import typing as tp
from dataclasses import dataclass
from urllib.parse import urlencode

import pydantic

from taskiq_dashboard.infrastructure.settings import BUILTIN_COLUMN_KEYS, ColumnSettings


logger = logging.getLogger(__name__)

BUILTIN_COLUMN_TITLES: dict[str, str] = {
    'id': 'Task ID',
    'name': 'Name',
    'status': 'Status',
    'worker': 'Worker',
    'started_at': 'Started At',
    'finished_at': 'Finished At',
    'runtime': 'Duration',
}

_FILTER_KINDS: dict[str, tp.Literal['search', 'text', 'status', 'datetime']] = {
    'id': 'search',
    'name': 'search',
    'status': 'status',
    'worker': 'text',
    'started_at': 'datetime',
    'finished_at': 'datetime',
}

_DATETIME_PARAMS: dict[str, tuple[str, str]] = {
    'started_at': ('start_date', 'end_date'),
    'finished_at': ('finished_start', 'finished_end'),
}

_SEARCH_PLACEHOLDERS = {
    frozenset({'id', 'name'}): 'Search by id or name',
    frozenset({'id'}): 'Search by id',
    frozenset({'name'}): 'Search by name',
}


class Column(pydantic.BaseModel):
    key: str
    title: str
    kind: tp.Literal['builtin', 'label']
    sortable: bool = False
    filterable: bool = False
    filter_kind: tp.Literal['search', 'text', 'status', 'datetime', 'none'] = 'none'


@dataclass(frozen=True)
class FilterControl:
    kind: tp.Literal['search', 'text', 'status', 'datetime']
    param: str
    end_param: str = ''
    title: str = ''
    placeholder: str = ''
    search_fields: tuple[str, ...] = ()
    column_key: str = ''
    in_header: bool = False


def build_columns(settings: ColumnSettings) -> list[Column]:
    filterable = set(settings.filterable)
    sortable = set(settings.sortable)
    columns: list[Column] = []
    for key in settings.visible:
        title = BUILTIN_COLUMN_TITLES.get(key)
        if title is None:
            logger.warning('Unknown column %r in columns.visible, skipping it', key)
            continue
        is_filterable = key in filterable
        columns.append(
            Column(
                key=key,
                title=title,
                kind='builtin',
                sortable=key in sortable,
                filterable=is_filterable,
                filter_kind=_filter_kind(key, 'builtin', filterable=is_filterable),
            )
        )

    for key, title in settings.labels.items():
        # A label key that matches a built-in column is configured through that built-in key.
        if key in BUILTIN_COLUMN_KEYS:
            continue
        is_filterable = key in filterable
        columns.append(
            Column(
                key=key,
                title=title,
                kind='label',
                sortable=key in sortable,
                filterable=is_filterable,
                filter_kind=_filter_kind(key, 'label', filterable=is_filterable),
            )
        )

    return columns


def build_filter_controls(settings: ColumnSettings) -> list[FilterControl]:
    columns = {column.key: column for column in build_columns(settings)}
    controls: list[FilterControl] = []
    search_emitted = False
    for key in settings.filterable:
        column = columns.get(key)
        if column is None or not column.filterable:
            continue
        if column.filter_kind == 'search':
            if search_emitted:
                continue
            search_keys = frozenset(candidate for candidate in ('id', 'name') if candidate in settings.filterable)
            controls.append(
                FilterControl(
                    kind='search',
                    param='q',
                    title='Search',
                    placeholder=_SEARCH_PLACEHOLDERS[search_keys],
                    search_fields=tuple(candidate for candidate in ('id', 'name') if candidate in search_keys),
                )
            )
            search_emitted = True
            continue
        if column.filter_kind == 'status':
            controls.append(
                FilterControl(kind='status', param='status', title=column.title, placeholder='All Statuses')
            )
            continue
        if column.filter_kind == 'datetime':
            param, end_param = _DATETIME_PARAMS[key]
            # started_at keeps the existing filter-bar picker. Any other datetime column
            # is filtered from its header so the bar does not grow another box.
            in_header = key != 'started_at'
            placeholder = ('Finished' if key == 'finished_at' else column.title) if in_header else 'Pick dates'
            controls.append(
                FilterControl(
                    kind='datetime',
                    param=param,
                    end_param=end_param,
                    title=column.title,
                    placeholder=placeholder,
                    column_key=key,
                    in_header=in_header,
                )
            )
            continue
        if column.filter_kind == 'text':
            param = f'label.{key}' if column.kind == 'label' else key
            controls.append(
                FilterControl(
                    kind='text',
                    param=param,
                    title=column.title,
                    placeholder=column.title,
                    column_key=key,
                    in_header=True,
                )
            )
    return controls


def resolve_sort(sort_by: str, settings: ColumnSettings) -> str | None:
    if sort_by in settings.sortable:
        return sort_by
    if settings.sortable:
        return settings.sortable[0]
    return None


def encode_list_query(base: dict[str, str], **overrides: object) -> str:
    params = dict(base)
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = str(value)
    return urlencode(params)


def _filter_kind(
    key: str,
    kind: tp.Literal['builtin', 'label'],
    *,
    filterable: bool,
) -> tp.Literal['search', 'text', 'status', 'datetime', 'none']:
    if not filterable:
        return 'none'
    if kind == 'label':
        return 'text'
    return _FILTER_KINDS.get(key, 'none')

import logging
import typing as tp
from dataclasses import dataclass
from urllib.parse import quote, urlencode

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

FilterKind = tp.Literal['search', 'combobox', 'text', 'status', 'datetime']

_FILTER_KINDS: dict[str, FilterKind] = {
    'id': 'search',
    'name': 'combobox',
    'status': 'status',
    'worker': 'combobox',
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
    filter_kind: FilterKind | tp.Literal['none'] = 'none'


@dataclass(frozen=True)
class FilterControl:
    kind: FilterKind
    param: str
    end_param: str = ''
    title: str = ''
    placeholder: str = ''
    search_fields: tuple[str, ...] = ()
    column_key: str = ''
    in_header: bool = False

    @property
    def match_param(self) -> str:
        return f'{self.param}_match'

    @property
    def dom_id(self) -> str:
        return quote(self.param, safe='')


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
                filter_kind=_FILTER_KINDS.get(key, 'none') if is_filterable else 'none',
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
                filter_kind='text' if is_filterable else 'none',
            )
        )

    return columns


def build_filter_controls(settings: ColumnSettings, columns: list[Column] | None = None) -> list[FilterControl]:
    by_key = {column.key: column for column in (build_columns(settings) if columns is None else columns)}
    controls: list[FilterControl] = []
    search_keys = frozenset(candidate for candidate in ('id', 'name') if candidate in settings.filterable)
    if search_keys:
        controls.append(
            FilterControl(
                kind='search',
                param='q',
                title='Search',
                placeholder=_SEARCH_PLACEHOLDERS[search_keys],
                search_fields=tuple(candidate for candidate in ('id', 'name') if candidate in search_keys),
            )
        )
    for key in settings.filterable:
        column = by_key.get(key)
        if column is None or not column.filterable:
            continue
        if column.filter_kind == 'search':
            continue
        if column.filter_kind == 'status':
            controls.append(
                FilterControl(
                    kind='status',
                    param='status',
                    title=column.title,
                    placeholder='All Statuses',
                    column_key=key,
                    in_header=True,
                )
            )
            continue
        if column.filter_kind == 'datetime':
            param, end_param = _DATETIME_PARAMS[key]
            controls.append(
                FilterControl(
                    kind='datetime',
                    param=param,
                    end_param=end_param,
                    title=column.title,
                    placeholder='Pick dates',
                    column_key=key,
                    in_header=True,
                )
            )
            continue
        if column.filter_kind in ('text', 'combobox'):
            param = f'label.{key}' if column.kind == 'label' else key
            controls.append(
                FilterControl(
                    kind=column.filter_kind,
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

import hashlib
import logging
import re
import typing as tp
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import sqlalchemy as sa

from taskiq_dashboard.infrastructure.settings import ColumnSettings


logger = logging.getLogger(__name__)

INDEX_PREFIX = 'ix_taskiq_dashboard__'
_NAME_RE = re.compile(r'^[a-z0-9_]+$')
_MAX_IDENTIFIER_LEN = 63
_DIRECT_TEXT_COLUMNS = frozenset({'name', 'worker'})
_BTREE_COLUMNS = frozenset({'status', 'started_at', 'finished_at'})


@dataclass(frozen=True)
class ManagedIndex:
    index: sa.Index
    uses_trgm: bool


def index_name(part: str, kind: str) -> str:
    raw = f'{INDEX_PREFIX}{part}__{kind}'
    if _NAME_RE.fullmatch(raw) and len(raw) <= _MAX_IDENTIFIER_LEN:
        return raw
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    safe = re.sub(r'[^a-z0-9_]+', '_', raw.lower()).strip('_')
    keep = _MAX_IDENTIFIER_LEN - len(digest) - 1
    return f'{safe[:keep]}_{digest}'


def build_managed_indexes(table: sa.Table, settings: ColumnSettings) -> list[ManagedIndex]:
    created: list[ManagedIndex] = []
    completed = False
    try:
        filterable = set(settings.filterable)
        sortable = set(settings.sortable)
        for key in dict.fromkeys([*settings.filterable, *settings.sortable]):
            created.extend(_indexes_for_key(table, settings, key, filterable=filterable, sortable=sortable))
        completed = True
        return created
    finally:
        if not completed:
            detach_managed_indexes(created)


@contextmanager
def managed_indexes(table: sa.Table, settings: ColumnSettings) -> Iterator[list[ManagedIndex]]:
    indexes = build_managed_indexes(table, settings)
    try:
        yield indexes
    finally:
        detach_managed_indexes(indexes)


def detach_managed_indexes(indexes: list[ManagedIndex]) -> None:
    for item in indexes:
        _detach(item.index)


def _indexes_for_key(
    table: sa.Table,
    settings: ColumnSettings,
    key: str,
    *,
    filterable: set[str],
    sortable: set[str],
) -> list[ManagedIndex]:
    if key in _BTREE_COLUMNS and (key in filterable or key in sortable):
        return [_btree(index_name(key, 'sort'), table.c[key])]
    if key == 'runtime' and key in sortable:
        return [_btree(index_name(key, 'sort'), table.c.finished_at - table.c.started_at)]
    if key == 'id' and key in filterable:
        return [_trgm_expression(index_name(key, 'trgm'), sa.cast(table.c.id, sa.String))]
    if key in _DIRECT_TEXT_COLUMNS:
        indexes: list[ManagedIndex] = []
        if key in sortable:
            indexes.append(_btree(index_name(key, 'sort'), table.c[key]))
        if key in filterable:
            indexes.append(_trgm_column(index_name(key, 'trgm'), table.c[key]))
        return indexes
    if key in settings.labels:
        part = f'label_{key}'
        indexes = []
        if key in sortable:
            indexes.append(_btree(index_name(part, 'sort'), table.c.labels[key].as_string()))
        if key in filterable:
            indexes.append(_trgm_expression(index_name(part, 'trgm'), table.c.labels[key].as_string()))
        return indexes
    return []


def _btree(name: str, expression: sa.ColumnElement[tp.Any]) -> ManagedIndex:
    return ManagedIndex(sa.Index(name, expression), uses_trgm=False)


def _trgm_column(name: str, column: sa.ColumnElement[tp.Any]) -> ManagedIndex:
    index = sa.Index(
        name,
        column,
        postgresql_using='gin',
        postgresql_ops={column.key: 'gin_trgm_ops'},
    )
    return ManagedIndex(index, uses_trgm=True)


def _trgm_expression(name: str, expression: sa.ColumnElement[tp.Any]) -> ManagedIndex:
    labeled = expression.label('trgm_target')
    index = sa.Index(
        name,
        labeled,
        postgresql_using='gin',
        postgresql_ops={'trgm_target': 'gin_trgm_ops'},
    )
    return ManagedIndex(index, uses_trgm=True)


def _detach(index: sa.Index) -> None:
    table = index.table
    if table is not None and index in table.indexes:
        table.indexes.remove(index)

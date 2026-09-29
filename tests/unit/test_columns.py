import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from taskiq_dashboard.api.columns import build_columns, build_filter_controls, resolve_sort
from taskiq_dashboard.infrastructure.database.indexes import INDEX_PREFIX, managed_indexes
from taskiq_dashboard.infrastructure.database.schemas import PostgresTask
from taskiq_dashboard.infrastructure.settings import ColumnSettings


def test_when_filterable_includes_runtime__then_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match='runtime'):
        ColumnSettings(filterable=['runtime'])


def test_when_filterable_column_is_not_displayed__then_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match=r'columns\.filterable'):
        ColumnSettings(
            visible=['id', 'name', 'status', 'started_at', 'finished_at', 'runtime'],
            filterable=['worker'],
        )


def test_when_sortable_column_is_not_displayed__then_settings_are_rejected() -> None:
    with pytest.raises(ValidationError, match=r'columns\.sortable'):
        ColumnSettings(visible=['id', 'name'], filterable=['id'], sortable=['runtime'])


def test_when_label_column_is_filterable_and_sortable__then_settings_are_accepted() -> None:
    settings = ColumnSettings(
        labels={'env': 'Env'},
        filterable=['id', 'name', 'status', 'started_at', 'env'],
        sortable=['started_at', 'finished_at', 'runtime', 'env'],
    )
    assert 'env' in settings.filterable
    assert 'env' in settings.sortable


def test_when_using_default_columns__then_filter_and_sort_flags_match_shipped_behavior() -> None:
    columns = {column.key: column for column in build_columns(ColumnSettings())}
    assert columns['worker'].filterable is False
    assert columns['worker'].sortable is False
    assert columns['name'].filterable is True
    assert columns['name'].sortable is False
    assert columns['name'].filter_kind == 'search'
    assert columns['status'].filter_kind == 'status'
    assert columns['started_at'].filterable is True
    assert columns['started_at'].sortable is True
    assert columns['started_at'].filter_kind == 'datetime'
    assert columns['runtime'].sortable is True
    assert columns['runtime'].filterable is False
    assert columns['runtime'].filter_kind == 'none'


def test_when_worker_and_label_are_configured__then_columns_are_filterable_and_sortable() -> None:
    columns = {
        column.key: column
        for column in build_columns(
            ColumnSettings(
                labels={'env': 'Env'},
                filterable=['id', 'worker', 'env', 'started_at'],
                sortable=['worker', 'env', 'started_at'],
            )
        )
    }
    assert columns['worker'].filterable is True
    assert columns['worker'].sortable is True
    assert columns['worker'].filter_kind == 'text'
    assert columns['env'].kind == 'label'
    assert columns['env'].filterable is True
    assert columns['env'].sortable is True
    assert columns['env'].filter_kind == 'text'


def test_when_building_filter_controls__then_id_and_name_share_one_search_box() -> None:
    controls = build_filter_controls(
        ColumnSettings(filterable=['worker', 'name', 'id', 'status', 'started_at', 'finished_at'])
    )
    assert [(control.kind, control.param, control.placeholder, control.in_header) for control in controls] == [
        ('text', 'worker', 'Worker', True),
        ('search', 'q', 'Search by id or name', False),
        ('status', 'status', 'All Statuses', False),
        ('datetime', 'start_date', 'Pick dates', False),
        ('datetime', 'finished_start', 'Finished', True),
    ]
    assert controls[0].column_key == 'worker'
    assert controls[4].column_key == 'finished_at'
    search = next(control for control in controls if control.kind == 'search')
    assert search.search_fields == ('id', 'name')


def test_when_only_name_is_filterable__then_search_box_searches_name() -> None:
    controls = build_filter_controls(ColumnSettings(visible=['id', 'name'], filterable=['name'], sortable=[]))
    assert len(controls) == 1
    assert controls[0].placeholder == 'Search by name'
    assert controls[0].search_fields == ('name',)


def test_when_sort_column_is_not_configured__then_fall_back_to_first_sortable_column() -> None:
    settings = ColumnSettings(sortable=['worker', 'name'])
    assert resolve_sort('missing', settings) == 'worker'
    assert resolve_sort('name', settings) == 'name'
    assert resolve_sort('started_at', ColumnSettings(sortable=[])) is None


def test_when_building_default_indexes__then_names_match_filterable_and_sortable_columns() -> None:
    settings = ColumnSettings()
    with managed_indexes(PostgresTask.__table__, settings) as indexes:
        names = {item.index.name for item in indexes}
        sql = {item.index.name: str(CreateIndex(item.index).compile(dialect=postgresql.dialect())) for item in indexes}
    assert names == {
        'ix_taskiq_dashboard__name__trgm',
        'ix_taskiq_dashboard__id__trgm',
        'ix_taskiq_dashboard__status__sort',
        'ix_taskiq_dashboard__started_at__sort',
        'ix_taskiq_dashboard__finished_at__sort',
        'ix_taskiq_dashboard__runtime__sort',
    }
    assert 'gin_trgm_ops' in sql['ix_taskiq_dashboard__id__trgm']
    assert 'gin_trgm_ops' in sql['ix_taskiq_dashboard__name__trgm']
    assert 'finished_at - started_at' in sql['ix_taskiq_dashboard__runtime__sort']
    assert not any(index.name.startswith(INDEX_PREFIX) for index in PostgresTask.__table__.indexes)


def test_when_worker_and_label_are_indexed__then_sort_and_trgm_indexes_are_created() -> None:
    settings = ColumnSettings(
        labels={'env': 'Env'},
        filterable=['worker', 'env'],
        sortable=['worker', 'env'],
        visible=['id', 'worker'],
    )
    with managed_indexes(PostgresTask.__table__, settings) as indexes:
        sql = {item.index.name: str(CreateIndex(item.index).compile(dialect=postgresql.dialect())) for item in indexes}
    assert set(sql) == {
        'ix_taskiq_dashboard__worker__sort',
        'ix_taskiq_dashboard__worker__trgm',
        'ix_taskiq_dashboard__label_env__sort',
        'ix_taskiq_dashboard__label_env__trgm',
    }
    assert "labels ->> 'env'" in sql['ix_taskiq_dashboard__label_env__sort']
    assert 'gin_trgm_ops' in sql['ix_taskiq_dashboard__worker__trgm']
    assert 'gin_trgm_ops' in sql['ix_taskiq_dashboard__label_env__trgm']
    assert not any(index.name.startswith(INDEX_PREFIX) for index in PostgresTask.__table__.indexes)

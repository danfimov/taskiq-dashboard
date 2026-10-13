import datetime as dt

import pytest

from taskiq_dashboard.api.columns import build_filter_controls
from taskiq_dashboard.api.routers.task import TaskFilter, _has_filters
from taskiq_dashboard.infrastructure.settings import ColumnSettings


class TestTaskFilter:
    def test_when_date_params_are_empty_strings__then_parsed_as_none(self) -> None:
        task_filter = TaskFilter(start_date='', end_date='')
        assert task_filter.start_date is None
        assert task_filter.end_date is None

    def test_when_date_params_are_iso_strings__then_parsed_as_datetime(self) -> None:
        task_filter = TaskFilter(start_date='2026-09-15T17:44', end_date='2026-09-15T17:50')
        assert task_filter.start_date == dt.datetime(2026, 9, 15, 17, 44)  # noqa: DTZ001
        assert task_filter.end_date == dt.datetime(2026, 9, 15, 17, 50)  # noqa: DTZ001


@pytest.mark.parametrize(('value', 'expected'), [('a ', False), (' a', False), ('  ', False), (' ab ', True)])
def test_when_search_is_trimmed__then_filter_indicator_matches_query(value, expected):
    controls = build_filter_controls(ColumnSettings())
    query = TaskFilter(q=value)
    assert query.q == value.strip()
    assert query.model_dump()['q'] == value.strip()
    assert _has_filters(query, controls, {}, {}) is expected


def test_when_exact_name_is_one_character__then_filter_indicator_is_active():
    controls = build_filter_controls(ColumnSettings())
    assert _has_filters(TaskFilter(name='x', name_match='exact'), controls, {'name': 'x'}, {})
    assert not _has_filters(TaskFilter(name='x'), controls, {'name': 'x'}, {})

import datetime as dt

from taskiq_dashboard.api.routers.task import TaskFilter


class TestTaskFilter:
    def test_when_date_params_are_empty_strings__then_parsed_as_none(self) -> None:
        task_filter = TaskFilter(start_date='', end_date='')  # ty: ignore[invalid-argument-type]

        assert task_filter.start_date is None
        assert task_filter.end_date is None

    def test_when_date_params_are_iso_strings__then_parsed_as_datetime(self) -> None:
        task_filter = TaskFilter(start_date='2026-09-15T17:44', end_date='2026-09-15T17:50')  # ty: ignore[invalid-argument-type]

        assert task_filter.start_date == dt.datetime(2026, 9, 15, 17, 44)  # noqa: DTZ001
        assert task_filter.end_date == dt.datetime(2026, 9, 15, 17, 50)  # noqa: DTZ001

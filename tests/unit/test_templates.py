import datetime as dt

from taskiq_dashboard.api.templates import format_duration


class TestFormatDuration:
    def test_when_started_at_is_none__then_return_none(self) -> None:
        assert format_duration(None, dt.datetime.now(dt.UTC)) is None

    def test_when_finished_at_is_none__then_return_none(self) -> None:
        assert format_duration(dt.datetime.now(dt.UTC), None) is None

    def test_when_duration_is_seconds__then_format_as_seconds(self) -> None:
        started_at = dt.datetime(2026, 9, 15, 12, 0, 0, tzinfo=dt.UTC)
        finished_at = started_at + dt.timedelta(seconds=45)
        assert format_duration(started_at, finished_at) == '45.0s'

    def test_when_duration_is_minutes__then_format_as_minutes_and_seconds(self) -> None:
        started_at = dt.datetime(2026, 9, 15, 12, 0, 0, tzinfo=dt.UTC)
        finished_at = started_at + dt.timedelta(seconds=125)
        assert format_duration(started_at, finished_at) == '2m 5s'

    def test_when_duration_is_hours__then_format_as_hours_and_minutes(self) -> None:
        started_at = dt.datetime(2026, 9, 15, 12, 0, 0, tzinfo=dt.UTC)
        finished_at = started_at + dt.timedelta(seconds=3725)
        assert format_duration(started_at, finished_at) == '1h 2m'

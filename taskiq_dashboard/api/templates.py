import datetime as dt
import pathlib
from zoneinfo import ZoneInfo

import markupsafe
from fastapi.templating import Jinja2Templates

from taskiq_dashboard.infrastructure.settings import get_settings


_timezone = get_settings().timezone


def format_datetime(value: dt.datetime | None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str | markupsafe.Markup | None:
    """Render a datetime according to the configured `timezone` setting."""
    if value is None:
        return None

    if _timezone == 'auto':
        return markupsafe.Markup('<time data-utc-time="{}">{}</time>').format(value.isoformat(), value.strftime(fmt))
    return value.astimezone(ZoneInfo(_timezone)).strftime(fmt)


def format_duration(started_at: dt.datetime | None, finished_at: dt.datetime | None) -> str | None:
    """Render the elapsed time between two datetimes as a compact human string, e.g. '1.2s', '3m 4s', '1h 2m'."""
    if started_at is None or finished_at is None:
        return None

    seconds = (finished_at - started_at).total_seconds()
    if seconds < 60:  # noqa: PLR2004
        return f'{seconds:.1f}s'
    minutes, seconds = divmod(int(seconds), 60)
    if minutes < 60:  # noqa: PLR2004
        return f'{minutes}m {seconds}s'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m'


_static_dir = pathlib.Path(__file__).parent / 'static'


def static_version(path: str) -> int:
    """Mtime of a static asset, used as a cache-busting query param so browsers refetch it after a rebuild."""
    return int((_static_dir / path).stat().st_mtime)


jinja_templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / 'templates')
jinja_templates.env.cache = None
jinja_templates.env.filters['format_datetime'] = format_datetime
jinja_templates.env.filters['format_duration'] = format_duration
jinja_templates.env.globals['is_auto_timezone'] = _timezone == 'auto'  # ty: ignore[invalid-assignment]
jinja_templates.env.globals['static_version'] = static_version  # ty: ignore[invalid-assignment]

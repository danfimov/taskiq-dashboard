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


_static_dir = pathlib.Path(__file__).parent / 'static'


def static_version(path: str) -> int:
    """Mtime of a static asset, used as a cache-busting query param so browsers refetch it after a rebuild."""
    return int((_static_dir / path).stat().st_mtime)


jinja_templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / 'templates')
jinja_templates.env.cache = None
jinja_templates.env.filters['format_datetime'] = format_datetime
jinja_templates.env.globals['is_auto_timezone'] = _timezone == 'auto'  # ty: ignore[invalid-assignment]
jinja_templates.env.globals['static_version'] = static_version  # ty: ignore[invalid-assignment]

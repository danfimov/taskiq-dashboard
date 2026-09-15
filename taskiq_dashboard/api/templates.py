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


jinja_templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / 'templates')
jinja_templates.env.cache = None
jinja_templates.env.filters['format_datetime'] = format_datetime
jinja_templates.env.globals['is_auto_timezone'] = _timezone == 'auto'  # ty: ignore[invalid-assignment]

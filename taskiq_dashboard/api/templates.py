import datetime as dt
import pathlib
from zoneinfo import ZoneInfo

import markupsafe
from fastapi.templating import Jinja2Templates

from taskiq_dashboard.infrastructure.settings import get_settings


def format_datetime(value: dt.datetime | None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str | markupsafe.Markup | None:
    """Render a datetime according to the configured `timezone` setting."""
    if value is None:
        return None

    timezone = get_settings().timezone
    if timezone == 'auto':
        return markupsafe.Markup('<time data-utc-time="{}">{}</time>').format(value.isoformat(), value.strftime(fmt))
    return value.astimezone(ZoneInfo(timezone)).strftime(fmt)


jinja_templates = Jinja2Templates(directory=pathlib.Path(__file__).parent / 'templates')
jinja_templates.env.cache = None
jinja_templates.env.filters['format_datetime'] = format_datetime
jinja_templates.env.globals['settings'] = get_settings()  # ty: ignore[invalid-assignment]

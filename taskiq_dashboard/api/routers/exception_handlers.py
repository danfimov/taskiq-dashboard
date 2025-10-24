import fastapi
from fastapi.responses import HTMLResponse

from taskiq_dashboard.api.templates import jinja_templates


async def exception_handler__not_found(
    request: fastapi.Request,
    __: fastapi.HTTPException,
) -> HTMLResponse:
    return jinja_templates.TemplateResponse(
        '404.html',
        {'request': request},
    )

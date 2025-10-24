import typing as tp

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from taskiq_dashboard.infrastructure import get_settings


class AccessTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: tp.Callable[[Request], tp.Awaitable[Response]]) -> Response:
        if not request.url.path.startswith('/api/'):
            return await call_next(request)

        token = request.headers.get('access-token')
        if not token:
            raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')

        settings = get_settings()
        if settings.api.token.get_secret_value() != token:
            raise HTTPException(status_code=401, detail='Invalid access token')
        return await call_next(request)

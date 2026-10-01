import hmac
import typing as tp

import fastapi

from taskiq_dashboard.infrastructure import get_settings


async def verify_access_token(
    access_token: tp.Annotated[str | None, fastapi.Header()] = None,
) -> None:
    """Reject requests unless the access-token header matches the configured token."""
    expected = get_settings().api.token.get_secret_value()
    if access_token is None or not hmac.compare_digest(access_token.encode(), expected.encode()):
        raise fastapi.HTTPException(status_code=401, detail='Invalid access token')

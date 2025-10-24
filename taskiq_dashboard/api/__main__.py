import asyncio
from logging import getLogger

import uvicorn

from taskiq_dashboard import dependencies
from taskiq_dashboard.api.application import get_app
from taskiq_dashboard.infrastructure.settings import Settings


logger = getLogger(__name__)


def main() -> None:
    """Entry point for the API part of application."""
    loop = asyncio.new_event_loop()
    application = get_app()
    settings = loop.run_until_complete(dependencies.container.get(Settings))
    uvicorn.run(
        application,
        host=settings.api.host,
        port=settings.api.port,
        reload=False,
        workers=1,
        lifespan='on',
        proxy_headers=True,
        forwarded_allow_ips='*',
        timeout_keep_alive=60,
        access_log=False,
    )


if __name__ == '__main__':
    main()

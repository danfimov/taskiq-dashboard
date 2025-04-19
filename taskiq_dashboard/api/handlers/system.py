import litestar
from litestar import response


@litestar.get("/ping")
async def ping() -> dict:
    """Health check endpoint."""
    return {"ping": "pong"}


@litestar.get("/")
async def redirect_to_docs() -> response.Redirect:
    """Redirect to API documentation."""
    return response.Redirect(path="/docs")


router = litestar.Router(
    path="/system",
    route_handlers=[ping],
)

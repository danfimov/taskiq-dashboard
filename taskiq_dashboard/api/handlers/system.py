import litestar


@litestar.get("/ping")
async def ping() -> dict:
    """Health check endpoint."""
    return {"ping": "pong"}


@litestar.get("/")
async def redirect_to_docs() -> litestar.response.Redirect:
    """Redirect to API documentation."""
    return litestar.response.Redirect(path="/docs")


router = litestar.Router(
    path="/system",
    route_handlers=[ping],
)

from taskiq_dashboard import dependencies
import litestar

def get_app() -> litestar.Litestar:
    return dependencies.get_server()

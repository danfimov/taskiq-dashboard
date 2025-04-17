from taskiq_dashboard import dependencies


def get_app():
    return dependencies.get_server()

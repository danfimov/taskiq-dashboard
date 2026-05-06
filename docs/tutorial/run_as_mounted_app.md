---
title: Run as a mounted app

---

Dashboard is just a web application so you can run it as a part of existing Fastapi app for example:

```python
from taskiq_dashboard import TaskiqDashboard
import fastapi

app = fastapi.FastAPI(...)
admin_dashboard = TaskiqDashboard(...)
app.mount('/admin', admin_dashboard.application)
```

One treaky thing is that your main app can't run lifespan function from `TaskiqDashboard` so you need to trigger it manually:

```python
from taskiq_dashboard import TaskiqDashboard
import fastapi

admin_dashboard = TaskiqDashboard(...)

@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> tp.AsyncGenerator[None, None]:
    dashboard_app = admin_dashboard.application
    async with dashboard_app.router.lifespan_context(dashboard_app):
        yield

app = fastapi.FastAPI(lifespan=lifespan)
app.mount('/admin', admin_dashboard.application)
```

You can see fully working example in [danfimov/taskiq-dashboard-example](https://github.com/danfimov/taskiq-dashboard-example) repository.

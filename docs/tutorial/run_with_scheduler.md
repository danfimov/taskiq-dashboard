---
title: Run with scheduler

---

You can run Taskiq Dashboard with scheduler.
By passing `scheduler` instance to the `TaskiqDashboard` constructor, you will get additional page at dashboard with scheduled tasks.

![interface with task actions](/assets/schedules.png)

In this example, we will demonstrate how to set up Taskiq Dashboard along with a task scheduler:

```python
--8<-- "docs/examples/example_with_scheduler.py"
```

To run this example, execute the following commands in different terminals:

1.  Run the worker:

    ```bash
    uv run taskiq worker docs.examples.example_with_scheduler:broker --workers 1
    ```

2. Run the admin panel:

    ```bash
    uv run python -m docs.examples.example_with_scheduler
    ```

3. Run the scheduler (optional, only for sending task):

    ```bash
    uv run taskiq scheduler docs.examples.example_with_scheduler:scheduler
    ```

After that, open your browser and navigate to `http://0.0.0.0:8000/schedules` to access the dashboard and see your scheduled task.

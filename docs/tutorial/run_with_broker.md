---
title: Run with broker

---

You can run Taskiq Dashboard with any broker.
By passing `broker` instance to the `TaskiqDashboard` constructor, you will get additional features like task actions.

![interface with task actions](/assets/task_actions.png)

In this example, we will demonstrate how to set up Taskiq Dashboard using a PostgreSQL broker along with a task scheduler:

```python
--8<-- "docs/examples/example_with_schedule_source.py"
```

To run this example, execute the following commands in different terminals:

1.  Run the worker:

    ```bash
    uv run taskiq worker docs.examples.example_with_schedule_source:broker --workers 1
    ```

2. Run the scheduler:

    ```bash
    uv run taskiq scheduler docs.examples.example_with_schedule_source:scheduler
    ```

3. Run the admin panel:

    ```bash
    uv run python -m docs.examples.example_with_schedule_source
    ```

After that, open your browser and navigate to `http://0.0.0.0:8000` to access the dashboard.

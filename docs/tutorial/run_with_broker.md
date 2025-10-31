---
title: Run with broker

---

You can run Taskiq Dashboard with any broker.
By passing `broker` instance to the `TaskiqDashboard` constructor, you will get additional features like task actions.

![interface with task actions](/assets/task_actions.png)

In this example, we will demonstrate how to set up Taskiq Dashboard using a PostgreSQL broker along with a task scheduler:

```python
--8<-- "docs/examples/example_with_broker.py"
```

To run this example, execute the following commands in different terminals:

1.  Run the worker:

    ```bash
    uv run taskiq worker docs.examples.example_with_broker:broker --workers 1
    ```

2. Run the admin panel:

    ```bash
    uv run python -m docs.examples.example_with_broker admin_panel
    ```


3. Send task:

    ```bash
    uv run python -m docs.examples.example_with_broker send_task
    ```


After that, open your browser and navigate to `http://0.0.0.0:8000` to access the dashboard and see your task.

---
title: Customizing Columns

---

The task list view shows a fixed set of columns by default. You can hide built-in columns you don't need and add custom columns backed by task [labels](https://taskiq-python.github.io/guide/labels.html).

## Configuration

Column behavior is configured using environment variables:

| Variable | Default | Description |
|----------|---------|--------------|
| `TASKIQ_DASHBOARD__COLUMNS__VISIBLE` | `["id", "name", "status", "worker", "started_at", "finished_at", "runtime"]` | Built-in columns to show, in order |
| `TASKIQ_DASHBOARD__COLUMNS__LABELS` | `{}` | Maps a task label key to the column title shown for it, appended after the built-in columns |

`id` must always be present in `TASKIQ_DASHBOARD__COLUMNS__VISIBLE` — it's the only column that links to the task details page, so the application refuses to start without it.

The `runtime` column (labeled "Duration") shows the elapsed time between `started_at` and `finished_at` (e.g. `3m 4s`) and can be sorted; tasks with no `finished_at` yet sort last.

### Hide unhelpful built-in columns

If `name` or `worker` is always the same value in your setup, drop it from the list:

```bash
export TASKIQ_DASHBOARD__COLUMNS__VISIBLE='["id", "status", "started_at", "finished_at"]'
```

### Show a label as a column

Given a task queued with `labels={"foo": "bar"}`, map `foo` to a column title in `TASKIQ_DASHBOARD__COLUMNS__LABELS`:

```bash
export TASKIQ_DASHBOARD__COLUMNS__LABELS='{"foo": "Foo"}'
```

Tasks that don't have that label show `-` in the corresponding cell.

## Limitations

- Label columns are not sortable — only `started_at`, `finished_at` and `runtime` support sorting.
- Column configuration is global (set at deployment time via environment variables), not per-user.

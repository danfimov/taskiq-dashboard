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
| `TASKIQ_DASHBOARD__COLUMNS__FILTERABLE` | `["id", "name", "status", "started_at"]` | Displayed columns that can be filtered |
| `TASKIQ_DASHBOARD__COLUMNS__SORTABLE` | `["started_at", "finished_at", "runtime"]` | Displayed columns whose headers can be sorted |

`id` must always be present in `TASKIQ_DASHBOARD__COLUMNS__VISIBLE`. It's the only column that links to the task details page, so the application refuses to start without it.

The `runtime` column (labeled "Duration") shows the elapsed time between `started_at` and `finished_at` (e.g. `3m 4s`). It can be sorted. It cannot be filtered, because the value is computed from `started_at` and `finished_at`. Tasks with no `finished_at` yet sort last.

A key in `FILTERABLE` or `SORTABLE` must be a column the list shows: a built-in key that is also in `VISIBLE`, or a key in `LABELS`. Any other key, including `runtime` in `FILTERABLE`, stops the application from starting.

`id` and `name`, when both are filterable, share one search box in the filter bar that matches either field. `status` stays a dropdown in that bar. `started_at` stays a date-range picker in that bar. Every other filterable column, including `worker`, `finished_at`, and label columns, shows a filter icon on its header. Text filters are case-insensitive and match a substring. Values shorter than 2 characters are ignored. Filters combine with AND.

Sort headers follow `SORTABLE`. An unknown `sort_by` in the URL falls back to the first entry in that list.

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

### Filter and sort `worker`

```bash
export TASKIQ_DASHBOARD__COLUMNS__FILTERABLE='["id", "name", "status", "worker", "started_at"]'
export TASKIQ_DASHBOARD__COLUMNS__SORTABLE='["worker", "started_at", "finished_at", "runtime"]'
```

Restart the dashboard. The Worker header shows a filter icon, and the header can be sorted.

### Filter and sort a label column

`env` has to be a shown column before it can be filtered or sorted:

```bash
export TASKIQ_DASHBOARD__COLUMNS__LABELS='{"env": "Env"}'
export TASKIQ_DASHBOARD__COLUMNS__FILTERABLE='["id", "name", "status", "worker", "env", "started_at"]'
export TASKIQ_DASHBOARD__COLUMNS__SORTABLE='["worker", "env", "started_at", "finished_at", "runtime"]'
```

The Environment header shows a filter icon. Label filters use the query parameter `label.<key>`, for example `label.env=prod`.

## Postgres indexes

When `storage_type` is `postgres`, startup creates and drops indexes so they match `FILTERABLE` and `SORTABLE`. SQLite does not add these indexes.

- Text contains filters (`id`, `name`, `worker`, and label columns) use a GIN trigram index (`pg_trgm`). Startup runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` when one of those indexes is needed. The database role must be allowed to create that extension.
- Sort, status equality, and datetime ranges use a btree index. A datetime or `status` column that is filterable, sortable, or both uses one btree.
- A text column that is both filterable and sortable gets both indexes.
- `runtime` uses a btree on `(finished_at - started_at)` when it is sortable.
- Label indexes are on `(labels->>'key')`.
- Index names use the prefix `ix_taskiq_dashboard__`. The next startup drops names under that prefix that the current config does not want. The primary key is left alone.

The default config creates indexes for the columns that are already filterable or sortable. `worker` gets `ix_taskiq_dashboard__worker__sort` and `ix_taskiq_dashboard__worker__trgm` only after it is listed. Removing it from both lists drops those indexes on the next startup.

## Limitations

- `runtime` can be sorted and cannot be filtered.
- Column configuration is global (set at deployment time via environment variables), not per-user.
- A label key that matches a built-in column name is not a separate column. Configure the built-in column instead.

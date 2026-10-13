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
| `TASKIQ_DASHBOARD__COLUMNS__MANAGE_INDEXES` | `false` | Opt in to creating PostgreSQL indexes at startup |

`id` must always be present in `TASKIQ_DASHBOARD__COLUMNS__VISIBLE`. It's the only column that links to the task details page, so the application refuses to start without it.

The `runtime` column (labeled "Duration") shows the elapsed time between `started_at` and `finished_at` (e.g. `3m 4s`). It can be sorted. It cannot be filtered, because the value is computed from `started_at` and `finished_at`. Tasks with no `finished_at` yet sort last.

When `FILTERABLE` or `SORTABLE` is omitted, its defaults are limited to displayed columns, so existing configurations that only customize `VISIBLE` continue to work. Explicitly configured lists remain strict: each key must be a built-in key in `VISIBLE`, or a key in `LABELS`. Any other explicit key, including `runtime` in `FILTERABLE`, stops the application from starting.

`id` and `name`, when both are filterable, share one global search box above the table that matches either field. Column-specific filters appear in their headers: `status` uses a dropdown, datetime columns use date ranges, labels use text fields, and `name` and `worker` use searchable comboboxes. Active values are shown beside the header filter icons. Text filters are case-insensitive and match a literal substring, including `%` and `_`. Leading and trailing whitespace is removed; values shorter than 2 characters after trimming are ignored. Filters combine with AND.

Name and Worker comboboxes initially suggest the 20 most recently seen distinct values, based on each value's most recent task queue timestamp (falling back to its start or finish timestamp). Typing searches values across all stored tasks, including older values outside the initial suggestions. Selecting an option applies a case-sensitive exact match; typing free text applies the substring filter. Editing a selection switches back to substring matching. The Clear filter button removes either mode.

Exact selections are represented in URLs as `name=<value>&name_match=exact` or `worker=<value>&worker_match=exact`. Selected values can be one character long and retain whitespace; the minimum-length and trimming rules apply to free-text substring filters.

Sort headers follow `SORTABLE`. An unknown `sort_by` in the URL falls back to the first entry in that list.
Label values sort as text, so `"10"` sorts before `"9"`. Task ID breaks ties and provides a stable order when `SORTABLE` is empty. Concurrent inserts, updates, or deletions can still shift offset-based pages.

### Hide unhelpful built-in columns

If `name` or `worker` is always the same value in your setup, drop it from the list:

```bash
export TASKIQ_DASHBOARD__COLUMNS__VISIBLE='["id", "status", "started_at", "finished_at"]'
export TASKIQ_DASHBOARD__COLUMNS__FILTERABLE='["id", "status", "started_at"]'
export TASKIQ_DASHBOARD__COLUMNS__SORTABLE='["started_at", "finished_at"]'
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

Index management is disabled by default. To enable it for PostgreSQL, set `TASKIQ_DASHBOARD__COLUMNS__MANAGE_INDEXES=true` and configure `TASKIQ_DASHBOARD__POSTGRES__INDEX_MANAGEMENT_DSN` with a direct PostgreSQL endpoint or a PgBouncer session pool. It must point to the same database and schema as the dashboard. For example:

```bash
export TASKIQ_DASHBOARD__COLUMNS__MANAGE_INDEXES=true
export TASKIQ_DASHBOARD__POSTGRES__INDEX_MANAGEMENT_DSN='postgresql+asyncpg://user:password@postgres:5432/dashboard'
```

Startup creates indexes for `FILTERABLE` and `SORTABLE` using `CREATE INDEX CONCURRENTLY IF NOT EXISTS` outside a transaction, on a separate connection that closes after use. One replica builds indexes while holding a session advisory lock; other replicas skip creation. The application's normal database connection can use PgBouncer transaction pooling, but the index management endpoint must not. If the separate DSN is absent, startup logs a warning and skips index management. Builds can still take time on large tables. SQLite does not add these indexes.

- Text contains filters (`id`, `name`, `worker`, and label columns) use a GIN trigram index (`pg_trgm`). Startup attempts `CREATE EXTENSION IF NOT EXISTS pg_trgm` when one of those indexes is needed. If the role cannot create the extension, startup logs a warning and skips trigram indexes; filters still work.
- Sort, status equality, and datetime ranges use a btree index. A datetime or `status` column that is filterable, sortable, or both uses one btree.
- A text column that is both filterable and sortable gets both indexes.
- `runtime` uses a btree on `(finished_at - started_at)` when it is sortable.
- Label indexes are on `(labels->>'key')`.
- Index names use the prefix `ix_taskiq_dashboard__`. Startup never drops existing indexes. Remove obsolete indexes explicitly after a deployment when they are no longer needed.

With index management enabled, the default column config creates six indexes for the columns that are already filterable or sortable. `worker` gets `ix_taskiq_dashboard__worker__sort` and `ix_taskiq_dashboard__worker__trgm` only after it is listed. Removing it from both lists retains those indexes.

GIN indexes add insert and update overhead, and a status index may provide little benefit when most rows share a status. Enable index management after measuring the read/write tradeoff, or leave it disabled and provision selected indexes separately. Index creation errors are logged without failing startup. A failed concurrent build can leave an invalid index; inspect it and rebuild or remove it explicitly before retrying.

## Limitations

- `runtime` can be sorted and cannot be filtered.
- Column configuration is global (set at deployment time via environment variables), not per-user.
- A label key that matches a built-in column name is not a separate column. Configure the built-in column instead.

---
title: Automatic Cleanup

---

Taskiq Dashboard automatically cleans up old tasks to prevent database bloat. This feature is **enabled by default** with safe defaults.

## Default Behavior

By default, the cleanup mechanism:

- Deletes tasks older than **30 days**;
- Keeps a maximum of **10,000 tasks** in the database;
- Runs at application startup;
- Runs periodically every **24 hours**.

## Configuration

You can configure cleanup behavior using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TASKIQ_DASHBOARD__CLEANUP__IS_ENABLED` | `true` | Enable or disable automatic cleanup |
| `TASKIQ_DASHBOARD__CLEANUP__TTL_DAYS` | `30` | Delete tasks older than this many days |
| `TASKIQ_DASHBOARD__CLEANUP__MAX_TASKS` | `10000` | Maximum number of tasks to keep |
| `TASKIQ_DASHBOARD__CLEANUP__PERIODIC_INTERVAL_HOURS` | `24` | How often to run periodic cleanup |
| `TASKIQ_DASHBOARD__CLEANUP__IS_CLEANUP_ON_STARTUP_ENANLED` | `true` | Run cleanup when application starts |

### Disable automatic cleanup

If you want to manage cleanup manually or through external tools:

```bash
export TASKIQ_DASHBOARD__CLEANUP__ENABLED=false
```

### Disable only startup cleanup

Run cleanup only periodically, not at startup:

```bash
export TASKIQ_DASHBOARD__CLEANUP__CLEANUP_ON_STARTUP=false
```

## How It Works

The cleanup process runs in two phases:

1. **TTL-based cleanup**: Deletes all tasks where the most recent timestamp (`finished_at`, `started_at`, or `queued_at`) is older than `TTL_DAYS`.
2. **Count-based cleanup**: If the total number of tasks exceeds `MAX_TASKS`, deletes the oldest tasks until the count is within the limit.

Both phases delete tasks regardless of their status. This prevents database bloat from stuck or abandoned tasks.

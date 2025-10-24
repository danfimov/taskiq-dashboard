#!/bin/sh

set -e

python -m taskiq_dashboard.infrastructure.database.migrations upgrade head

exec "$@"

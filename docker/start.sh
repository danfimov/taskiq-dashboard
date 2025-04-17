#!/bin/sh

set -e

export LITESTAR_APP=taskiq_dashboard.api:app

echo "Starting API server"
litestar run --host "0.0.0.0" --port "80"

exec "$@"

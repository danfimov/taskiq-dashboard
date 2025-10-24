#!/bin/sh

set -e

echo "Starting API server with taskiq dashboard..."
python -m taskiq_dashboard.api

exec "$@"

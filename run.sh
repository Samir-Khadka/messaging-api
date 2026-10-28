#!/bin/sh
# Start the Messaging API (from the project root).
# Usage: ./run.sh            (port 8000)
#        PORT=9000 ./run.sh  (custom port)
set -e
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

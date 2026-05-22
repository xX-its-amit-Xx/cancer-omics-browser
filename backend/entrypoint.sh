#!/usr/bin/env bash
set -e

# Create tables + load data (synthetic by default, GDC if DATA_SOURCE=gdc).
python -m ingest.run

# Serve the API. Render (and similar hosts) inject $PORT; default to 8000 locally.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

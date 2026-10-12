#!/bin/bash
echo "Mildoc Admin Starting... "

uv sync

nohup uv run gunicorn -c gunicorn.config.py admin_api:app >> mildoc_admin.log 2>&1 &

echo $! > mildoc_admin.pid
echo "Mildoc Admin started, PID: $(cat mildoc_admin.pid)"